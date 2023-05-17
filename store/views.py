import django
from django.contrib.auth.models import User
from store.models import Address, Cart, Category, Order, Product, Review

from django.db.models import Count
from django.db.models.functions import ExtractMonth

from django.shortcuts import redirect, render, get_object_or_404
from .forms import RegistrationForm, AddressForm, ReviewForm
from django.contrib import messages
from django.views import View
import decimal
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator # for Class Based Views

import io
from django.http import FileResponse
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import pywhatkit as pwk

# Create your views here.

def home(request):
    categories = Category.objects.filter(is_active=True, is_featured=True)[:3]
    products = Product.objects.filter(is_active=True, is_featured=True)[:8]
    context = {
        'categories': categories,
        'products': products,
    }
    return render(request, 'store/index.html', context)

def blog(request):
     return render(request, 'account/blog.html')

def detail(request, slug):
    reviewes = Review.objects.filter(user=request.user)
    product = get_object_or_404(Product, slug=slug)
    related_products = Product.objects.exclude(id=product.id).filter(is_active=True, category=product.category)
    context = {
        'product': product,
        'related_products': related_products,
	'reviewes': reviewes,
    }
    return render(request, 'store/detail.html', context)


def all_categories(request):
    categories = Category.objects.filter(is_active=True)
    return render(request, 'store/categories.html', {'categories':categories})


def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(is_active=True, category=category)
    categories = Category.objects.filter(is_active=True)
    context = {
        'category': category,
        'products': products,
        'categories': categories,
    }
    return render(request, 'store/category_products.html', context)


# Authentication Starts Here

class RegistrationView(View):
    def get(self, request):
        form = RegistrationForm()
        return render(request, 'account/register.html', {'form': form})
    
    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            messages.success(request, "Congratulations! Registration Successful!")
            form.save()
        return render(request, 'account/register.html', {'form': form})
        
import calendar
@login_required
def profile(request):
    addresses = Address.objects.filter(user=request.user)
    orders = Order.objects.filter(user=request.user)
    orders1 = Order.objects.annotate(month=ExtractMonth('ordered_date')).values('month').annotate(count=Count('id')).values('month','count') 
    monthNumber = []
    totalOrder = []
    for d in orders1:
       monthNumber.append(calendar.month_name[d['month']])
       totalOrder.append(d['count'])
    return render(request, 'account/profile.html', {'addresses':addresses, 'orders':orders, 'monthNumber':monthNumber, 'totalOrder':totalOrder})



@method_decorator(login_required, name='dispatch')
class AddressView(View):
    def get(self, request):
        form = AddressForm()
        return render(request, 'account/add_address.html', {'form': form})

    def post(self, request):
        form = AddressForm(request.POST)
        if form.is_valid():
            user=request.user
            locality = form.cleaned_data['locality']
            city = form.cleaned_data['city']
            state = form.cleaned_data['state']
            reg = Address(user=user, locality=locality, city=city, state=state)
            reg.save()
            messages.success(request, "New Address Added Successfully.")
            return redirect('store:profile')

@method_decorator(login_required, name='dispatch')
class ReviewView(View):
    def get(self, request):
        form = ReviewForm()
        return render(request, 'account/review.html', {'form': form})

    def post(self, request):
     form = ReviewForm(request.POST)
     if form.is_valid():
        user=request.user
        name = form.cleaned_data['name']
        review = form.cleaned_data['review']
        rating = form.cleaned_data['rating']
        reg = Review(user=user, name=name, review=review, rating=rating)
        reg.save()
        messages.success(request, "New Review Added Successfully.")
        return render(request, 'account/review.html')

@login_required
def remove_address(request, id):
    a = get_object_or_404(Address, user=request.user, id=id)
    a.delete()
    messages.success(request, "Address removed.")
    return redirect('store:profile')


@login_required
def add_to_cart(request):
    user = request.user
    product_id = request.GET.get('prod_id')
    product = get_object_or_404(Product, id=product_id)

    # Check whether the Product is alread in Cart or Not
    item_already_in_cart = Cart.objects.filter(product=product_id, user=user)
    if item_already_in_cart:
        cp = get_object_or_404(Cart, product=product_id, user=user)
        cp.quantity += 1
        cp.save()
    else:
        Cart(user=user, product=product).save()
    
    return redirect('store:cart')


@login_required
def cart(request):
    user = request.user
    cart_products = Cart.objects.filter(user=user)

    # Display Total on Cart Page
    amount = decimal.Decimal(0)
    shipping_amount = decimal.Decimal(10)
    # using list comprehension to calculate total amount based on quantity and shipping
    cp = [p for p in Cart.objects.all() if p.user==user]
    if cp:
        for p in cp:
            temp_amount = (p.quantity * p.product.price)
            amount += temp_amount

    # Customer Addresses
    addresses = Address.objects.filter(user=user)

    context = {
        'cart_products': cart_products,
        'amount': amount,
        'shipping_amount': shipping_amount,
        'total_amount': amount + shipping_amount,
        'addresses': addresses,
    }
    return render(request, 'store/cart.html', context)


@login_required
def remove_cart(request, cart_id):
    if request.method == 'GET':
        c = get_object_or_404(Cart, id=cart_id)
        c.delete()
        messages.success(request, "Product removed from Cart.")
    return redirect('store:cart')


@login_required
def plus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        cp.quantity += 1
        cp.save()
    return redirect('store:cart')


@login_required
def minus_cart(request, cart_id):
    if request.method == 'GET':
        cp = get_object_or_404(Cart, id=cart_id)
        # Remove the Product if the quantity is already 1
        if cp.quantity == 1:
            cp.delete()
        else:
            cp.quantity -= 1
            cp.save()
    return redirect('store:cart')



@login_required
def checkout(request):
    user = request.user
    address_id = request.GET.get('address')
    
    address = get_object_or_404(Address, id=address_id)
    # Get all the products of User in Cart
    cart = Cart.objects.filter(user=user)
    for c in cart:
        # Saving all the products from Cart to Order
        Order(user=user, address=address, product=c.product, quantity=c.quantity).save()
        # And Deleting from Cart
        c.delete()
    return redirect('store:orders')



def shop(request):
    return render(request, 'store/shop.html')


def test(request):
    return render(request, 'store/test.html')


@login_required
def orders(request):
    all_orders = Order.objects.filter(user=request.user).order_by('-ordered_date')
    pwk.sendwhatmsg_instantly("+918825658017", "Test msg.", 10, tab_close=True)
    return render(request, 'store/orders.html', {'orders': all_orders})



def some_view(request):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer)
    c.translate(inch,inch)
# define a large font
    c.setFont("Helvetica", 14)
# choose some colors
    c.setStrokeColorRGB(0.1,0.8,0.1)
    c.setFillColorRGB(0,0,1) # font colour
    c.drawImage('F:\\adbricks media\\ecomm\\static\\img\\logo.jpg',-0.8*inch,9.3*inch)
    c.drawString(0, 9*inch, "Shop Name :AdBrick Media ")
    c.drawString(0, 8.7*inch, "City Name:Kumananchavadi, Chennai-600056")
    c.setFillColorRGB(0,0,0) # font colour
    c.line(0,8.6*inch,6.8*inch,8.6*inch)
    c.drawString(5.6*inch,9.5*inch,'Bill No :# 1234')
    from  datetime import date
    dt = date.today().strftime('%d-%b-%Y')
    c.drawString(5.6*inch,9.3*inch,dt)
    c.setFont("Helvetica", 8)
    #c.drawString(3*inch,9.6*inch,'ORDER INVOICE')
    c.setFillColorRGB(1,0,0) # font colour
    c.setFont("Times-Bold", 40)
    c.drawString(4.3*inch,8.7*inch,'INVOICE')
    c.rotate(45) # rotate by 45 degree 
    c.setFillColorCMYK(0,0,0,0.08) # font colour CYAN, MAGENTA, YELLOW and BLACK
    c.setFont("Helvetica", 140) # font style and size
    c.drawString(2*inch, 1*inch, "SAMPLE") # String written 
    c.rotate(-45) # restore the rotation 
    c.setFillColorRGB(0,0,0) # font colour
    c.setFont("Times-Roman", 22)
    c.drawString(0.5*inch,8.3*inch,'Products')
    c.drawString(4*inch,8.3*inch,'Price')
    c.drawString(5*inch,8.3*inch,'Quantity')
    c.drawString(6.1*inch,8.3*inch,'Total')
    c.setStrokeColorCMYK(0,0,0,1) # vertical line colour 
    c.line(3.9*inch,8.3*inch,3.9*inch,2.7*inch)# first vertical line
    c.line(4.9*inch,8.3*inch,4.9*inch,2.7*inch)# second vertical line
    c.line(6.1*inch,8.3*inch,6.1*inch,2.7*inch)# third vertical line
    c.line(0.01*inch,2.5*inch,7*inch,2.5*inch)# horizontal line total

    c.drawString(1*inch,1.8*inch,'Shopping Charge')
    c.setFont("Times-Bold", 22)
    c.drawString(2*inch,0.8*inch,'Total')
    c.setFont("Times-Roman", 22)
    c.setStrokeColorRGB(0.1,0.8,0.1) # Bottom Line colour 
    c.line(0,-0.7*inch,6.8*inch,-0.7*inch)
    c.setFont("Helvetica", 8) # font size
    c.setFillColorRGB(1,0,0) # font colour
    c.drawString(0, -0.9*inch, u"\u00A9"+" sales@adbricksmedia.com")

    line_y=7.9
    c.setFont("Times-Bold", 22)
    c.setFillColorRGB(1,0,0)
    c.drawString(0.1*inch,line_y*inch,'Square Banner') # p Name
    c.drawRightString(4.5*inch,line_y*inch,'4000') # p Price
    c.drawRightString(5.5*inch,line_y*inch,'1') # p Qunt 
    c.drawRightString(7*inch,line_y*inch,'4000') # Sub Total 
    c.drawRightString(7*inch,1.8*inch,'+ 10')
    c.drawRightString(7*inch,0.8*inch,'4010')
    c.showPage()
    c.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename="invoice.pdf")
