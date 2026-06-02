from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'accounts'

router = DefaultRouter()
router.register('addresses', views.AddressViewSet, basename='address')

urlpatterns = [
    path('', include(router.urls)),
    # Authentication endpoints
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Profile endpoints
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Rider specific endpoints
    path('rider/location/', views.RiderLocationView.as_view(), name='rider_location'),
    path('rider/status/', views.RiderStatusView.as_view(), name='rider_status'),
    
    # Admin endpoints
    path('admin/users/', views.UserListView.as_view(), name='admin_user_list'),
    path('admin/users/<int:pk>/', views.UserDetailView.as_view(), name='admin_user_detail'),
]