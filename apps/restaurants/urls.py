from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'restaurants'

router = DefaultRouter()
router.register('restaurants', views.RestaurantViewSet, basename='restaurant')
router.register('categories', views.MenuCategoryViewSet, basename='menu-category')
router.register('menu-items', views.MenuItemViewSet, basename='menu-item')

urlpatterns = [
    path('', include(router.urls)),
]
