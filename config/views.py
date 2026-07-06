from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.views.decorators.http import require_POST
from apps.accounts.models import User, Address
from apps.restaurants.models import Restaurant, RestaurantReview, FavoriteRestaurant, MenuItem
from apps.orders.models import Order, Cart, CartItem, OrderItem
from django.utils import timezone
from django.db.models import Sum, Avg, Q
from urllib.parse import urlparse


def _is_safe_url(url):
    """Validate that a URL is safe (relative path, no external redirects)."""
    if not url:
        return False
    parsed = urlparse(url)
    return not parsed.scheme and not parsed.netloc and url.startswith('/')

def index(request):
    city = request.GET.get('city')
    search = request.GET.get('search')
    cuisine = request.GET.get('cuisine')

    active_address = None
    if request.user.is_authenticated:
        active_address = Address.objects.filter(user=request.user, is_active=True).first()
        if not city and active_address:
            city = active_address.city

    restaurants = Restaurant.objects.filter(is_active=True, is_verified=True)

    # Filter by location if active address is set
    if active_address and not request.GET.get('city'):
        # Filter within a roughly 10km radius (approx 0.1 degree)
        lat = float(active_address.latitude)
        lng = float(active_address.longitude)
        restaurants = restaurants.filter(
            latitude__gte=lat - 0.1,
            latitude__lte=lat + 0.1,
            longitude__gte=lng - 0.1,
            longitude__lte=lng + 0.1
        )

    if city:
        restaurants = restaurants.filter(city=city)
    if cuisine:
        restaurants = restaurants.filter(cuisine_type=cuisine)
    if search:
        restaurants = restaurants.filter(
            Q(name__icontains=search) |
            Q(cuisine_type__icontains=search) |
            Q(menu_items__name__icontains=search) |
            Q(menu_items__description__icontains=search)
        ).distinct()

    cities = Restaurant.objects.values_list('city', flat=True).distinct()
    cuisines = Restaurant.CuisineType.choices

    return render(request, 'index.html', {
        'restaurants': restaurants,
        'cities': cities,
        'cuisines': cuisines,
        'current_city': city,
        'current_cuisine': cuisine,
        'active_address': active_address
    })

def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next')
    if not _is_safe_url(next_url):
        next_url = None

    if request.user.is_authenticated:
        if next_url:
            return redirect(next_url)
        if request.user.is_staff or request.user.role == User.Role.ADMIN:
            return redirect('admin_dashboard')
        elif request.user.role == User.Role.RESTAURANT_OWNER:
            return redirect('owner_dashboard')
        else:
            return redirect('customer_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            if next_url:
                return redirect(next_url)
            if user.is_staff or user.role == User.Role.ADMIN:
                return redirect('admin_dashboard')
            elif user.role == User.Role.RESTAURANT_OWNER:
                return redirect('owner_dashboard')
            else:
                return redirect('customer_dashboard')
        else:
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')

    return render(request, 'login.html', {'next': next_url})

def logout_view(request):
    auth_logout(request)
    return redirect('index')

def register_view(request):
    if request.method == 'POST':
        # Using a simple custom registration for this demo
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role', 'customer')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'نام کاربری تکراری است.')
        else:
            user = User.objects.create_user(username=username, email=email, password=password, role=role)
            auth_login(request, user)
            messages.success(request, 'ثبت نام با موفقیت انجام شد.')
            if role == 'restaurant_owner':
                return redirect('owner_dashboard')
            return redirect('customer_dashboard')

    return render(request, 'register.html')

@login_required
def profile_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'رمز عبور شما با موفقیت تغییر کرد.')
            return redirect('profile')
        else:
            messages.error(request, 'لطفا خطاهای زیر را برطرف کنید.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'profile.html', {'form': form})

@login_required
def customer_dashboard(request):
    active_address = Address.objects.filter(user=request.user, is_active=True).first()
    city = request.GET.get('city') or (active_address.city if active_address else None)

    restaurants = Restaurant.objects.filter(is_active=True, is_verified=True)

    if active_address and not request.GET.get('city'):
        lat = float(active_address.latitude)
        lng = float(active_address.longitude)
        restaurants = restaurants.filter(
            latitude__gte=lat - 0.1,
            latitude__lte=lat + 0.1,
            longitude__gte=lng - 0.1,
            longitude__lte=lng + 0.1
        )
    elif city:
        restaurants = restaurants.filter(city=city)

    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    favorites = FavoriteRestaurant.objects.filter(user=request.user).select_related('restaurant')
    cities = Restaurant.objects.values_list('city', flat=True).distinct()
    addresses = Address.objects.filter(user=request.user)

    return render(request, 'customer/dashboard.html', {
        'restaurants': restaurants,
        'orders': orders,
        'favorites': favorites,
        'cities': cities,
        'current_city': city,
        'addresses': addresses,
        'active_address': active_address
    })

@login_required
def add_address(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        city = request.POST.get('city')
        address_text = request.POST.get('address_text')
        lat = request.POST.get('latitude', 0)
        lng = request.POST.get('longitude', 0)

        is_first = not Address.objects.filter(user=request.user).exists()

        Address.objects.create(
            user=request.user,
            title=title,
            city=city,
            address_text=address_text,
            latitude=lat,
            longitude=lng,
            is_default=is_first,
            is_active=is_first
        )
        messages.success(request, 'آدرس با موفقیت اضافه شد.')
    return redirect('customer_dashboard')

@login_required
@require_POST
def delete_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    address.delete()
    messages.success(request, 'آدرس حذف شد.')
    return redirect('customer_dashboard')

@login_required
@require_POST
def set_active_address(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    Address.objects.filter(user=request.user).update(is_active=False)
    address.is_active = True
    address.save()
    messages.success(request, f'آدرس فعال به {address.title} تغییر یافت.')
    return redirect('customer_dashboard')

@login_required
@require_POST
def add_to_cart(request, item_id):
    menu_item = get_object_or_404(MenuItem, id=item_id)
    cart, _ = Cart.objects.get_or_create(customer=request.user)

    # Check if adding item from a different restaurant
    if cart.items.exists():
        first_item = cart.items.first()
        if first_item.menu_item.restaurant != menu_item.restaurant:
            # For simplicity, we clear the cart if from a different restaurant
            cart.items.all().delete()

    cart_item, created = CartItem.objects.get_or_create(cart=cart, menu_item=menu_item)
    if not created:
        cart_item.quantity += 1
        cart_item.save()

    return redirect('restaurant_detail', pk=menu_item.restaurant.id)

@login_required
def cart_view(request):
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    return render(request, 'cart.html', {'cart': cart})

@login_required
@require_POST
def remove_from_cart(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, cart__customer=request.user)
    cart_item.delete()
    return redirect('cart_view')

@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, customer=request.user)

    # Progress percentage based on status
    status_map = {
        Order.Status.PENDING: 10,
        Order.Status.CONFIRMED: 25,
        Order.Status.PREPARING: 50,
        Order.Status.READY: 75,
        Order.Status.DELIVERING: 90,
        Order.Status.DELIVERED: 100,
        Order.Status.CANCELLED: 0,
        Order.Status.REJECTED: 0,
    }
    progress = status_map.get(order.status, 0)

    return render(request, 'customer/order_detail.html', {
        'order': order,
        'progress': progress
    })

@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    if not cart.items.exists():
        messages.error(request, "سبد خرید شما خالی است.")
        return redirect('index')

    addresses = Address.objects.filter(user=request.user)
    active_address = addresses.filter(is_active=True).first() or addresses.filter(is_default=True).first()

    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        if address_id:
            selected_address = get_object_or_404(Address, id=address_id, user=request.user)
            address_text = selected_address.address_text
            lat = selected_address.latitude
            lng = selected_address.longitude
        else:
            address_text = request.POST.get('address')
            lat = 0
            lng = 0

        restaurant = cart.items.first().menu_item.restaurant

        # Calculate delivery fee
        from apps.delivery.services import DeliveryFeeCalculator
        restaurant_location = restaurant.get_location()
        fee_result = DeliveryFeeCalculator.calculate_fee(
            restaurant_lat=float(restaurant_location[0]) if restaurant_location else 0,
            restaurant_lng=float(restaurant_location[1]) if restaurant_location else 0,
            customer_lat=float(lat) if lat else 0,
            customer_lng=float(lng) if lng else 0,
        )

        # Create Order
        order = Order.objects.create(
            customer=request.user,
            restaurant=restaurant,
            delivery_address=address_text,
            subtotal=cart.total,
            delivery_fee=fee_result['delivery_fee'],
            total_amount=cart.total + fee_result['delivery_fee'],
            customer_latitude=lat,
            customer_longitude=lng,
            distance_km=fee_result['distance_km']
        )

        # Create Order Items and deduct stock
        for item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                menu_item=item.menu_item,
                quantity=item.quantity,
                price=item.menu_item.price,
                item_name=item.menu_item.name,
                item_description=item.menu_item.description
            )
            item.menu_item.deduct_stock()

        # Increment restaurant order count
        restaurant.current_orders_count += 1
        restaurant.save(update_fields=['current_orders_count'])

        # Clear Cart
        cart.items.all().delete()

        messages.success(request, "سفارش شما با موفقیت ثبت شد.")
        return redirect('customer_dashboard')

    return render(request, 'checkout.html', {'cart': cart})

@login_required
def restaurant_detail(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)
    menu_items = restaurant.menu_items.filter(is_available=True)
    reviews = restaurant.reviews.all().order_by('-created_at')
    is_favorite = FavoriteRestaurant.objects.filter(user=request.user, restaurant=restaurant).exists()

    if request.method == 'POST' and 'rating' in request.POST:
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        RestaurantReview.objects.update_or_create(
            restaurant=restaurant, user=request.user,
            defaults={'rating': rating, 'comment': comment}
        )
        return redirect('restaurant_detail', pk=pk)

    return render(request, 'restaurant_detail.html', {
        'restaurant': restaurant,
        'menu_items': menu_items,
        'reviews': reviews,
        'is_favorite': is_favorite
    })

@login_required
@require_POST
def toggle_favorite(request, pk):
    restaurant = get_object_or_404(Restaurant, pk=pk)
    favorite, created = FavoriteRestaurant.objects.get_or_create(user=request.user, restaurant=restaurant)
    if not created:
        favorite.delete()
    return redirect('restaurant_detail', pk=pk)

@login_required
def owner_dashboard(request):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    orders = Order.objects.filter(restaurant=restaurant).order_by('-created_at')[:10]

    # Simple report data
    today = timezone.now().date()
    today_orders = Order.objects.filter(restaurant=restaurant, created_at__date=today)
    report = {
        'total_revenue': today_orders.filter(status=Order.Status.DELIVERED).aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
        'pending_orders': today_orders.filter(status=Order.Status.PENDING).count()
    }

    return render(request, 'owner/dashboard.html', {
        'restaurant': restaurant,
        'orders': orders,
        'report': report
    })

@login_required
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.role == User.Role.ADMIN):
        return render(request, '403.html', status=403)

    user_count = User.objects.count()
    restaurant_count = Restaurant.objects.filter(is_active=True).count()
    today = timezone.now().date()
    today_orders = Order.objects.filter(created_at__date=today).count()
    online_riders = User.objects.filter(role=User.Role.DELIVERY_RIDER, rider_status=User.RiderStatus.AVAILABLE).count()

    pending_restaurants = Restaurant.objects.filter(is_verified=False)

    return render(request, 'admin/dashboard.html', {
        'user_count': user_count,
        'restaurant_count': restaurant_count,
        'today_orders': today_orders,
        'online_riders': online_riders,
        'pending_restaurants': pending_restaurants
    })


# === Owner Action Views ===

@login_required
@require_POST
def owner_toggle_status(request):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    if restaurant:
        restaurant.is_open = not restaurant.is_open
        restaurant.save(update_fields=['is_open'])
        status_text = 'open' if restaurant.is_open else 'closed'
        messages.success(request, f'Restaurant is now {status_text}.')
    return redirect('owner_dashboard')

@login_required
@require_POST
def owner_confirm_order(request, pk):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    if order.status == Order.Status.PENDING:
        order.update_status(Order.Status.CONFIRMED)
        messages.success(request, f'Order #{order.order_number} confirmed.')
    return redirect('owner_dashboard')

@login_required
@require_POST
def owner_start_preparing(request, pk):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    if order.status == Order.Status.CONFIRMED:
        order.update_status(Order.Status.PREPARING)
        messages.success(request, f'Order #{order.order_number} is now being prepared.')
    return redirect('owner_dashboard')

@login_required
@require_POST
def owner_mark_ready(request, pk):
    restaurant = Restaurant.objects.filter(owner=request.user).first()
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    if order.status == Order.Status.PREPARING:
        order.update_status(Order.Status.READY)
        messages.success(request, f'Order #{order.order_number} is ready for delivery.')
    return redirect('owner_dashboard')


# === Admin Action Views ===

@login_required
@require_POST
def admin_verify_restaurant(request, pk):
    if not (request.user.is_staff or request.user.role == User.Role.ADMIN):
        messages.error(request, 'Permission denied.')
        return redirect('index')
    restaurant = get_object_or_404(Restaurant, pk=pk)
    restaurant.is_verified = True
    restaurant.save(update_fields=['is_verified'])
    messages.success(request, f'Restaurant "{restaurant.name}" has been verified.')
    return redirect('admin_dashboard')
