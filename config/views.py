from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib import messages
from apps.accounts.models import User
from apps.restaurants.models import Restaurant, RestaurantReview, FavoriteRestaurant
from apps.orders.models import Order
from django.utils import timezone
from django.db.models import Sum, Avg

def index(request):
    return render(request, 'index.html')

def login_view(request):
    if request.user.is_authenticated:
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
            if user.is_staff or user.role == User.Role.ADMIN:
                return redirect('admin_dashboard')
            elif user.role == User.Role.RESTAURANT_OWNER:
                return redirect('owner_dashboard')
            else:
                return redirect('customer_dashboard')
        else:
            messages.error(request, 'نام کاربری یا رمز عبور اشتباه است.')
    return render(request, 'login.html')

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
    restaurants = Restaurant.objects.filter(is_active=True, is_verified=True)
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    favorites = FavoriteRestaurant.objects.filter(user=request.user).select_related('restaurant')
    return render(request, 'customer/dashboard.html', {
        'restaurants': restaurants,
        'orders': orders,
        'favorites': favorites
    })

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
