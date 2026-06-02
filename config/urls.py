"""
URL configuration for DanialFood project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from . import views

urlpatterns = [
    # Web Panels
    path('', views.index, name='index'),
    path('login/', views.login_view, name='web_login'),
    path('logout/', views.logout_view, name='web_logout'),
    path('register/', views.register_view, name='web_register'),
    path('profile/', views.profile_view, name='profile'),
    path('restaurant/<int:pk>/', views.restaurant_detail, name='restaurant_detail'),
    path('restaurant/<int:pk>/favorite/', views.toggle_favorite, name='toggle_favorite'),
    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),
    path('address/add/', views.add_address, name='add_address'),
    path('address/delete/<int:pk>/', views.delete_address, name='delete_address'),
    path('address/set-active/<int:pk>/', views.set_active_address, name='set_active_address'),
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order/<int:pk>/', views.order_detail, name='order_detail'),
    path('dashboard/owner/', views.owner_dashboard, name='owner_dashboard'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),

    # Admin panel
    path('admin/', admin.site.urls),
    
    # API endpoints
    path('api/auth/', include('apps.accounts.urls')),
    path('api/restaurants/', include('apps.restaurants.urls')),
    path('api/orders/', include('apps.orders.urls')),
    path('api/delivery/', include('apps.delivery.urls')),
    
    # API Schema & Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
