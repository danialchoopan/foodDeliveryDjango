from rest_framework import generics, viewsets, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Q, F, Count, Avg
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from geopy.distance import distance

from .models import Restaurant, MenuCategory, MenuItem
from .serializers import (
    RestaurantListSerializer, RestaurantDetailSerializer, RestaurantCreateUpdateSerializer,
    MenuCategorySerializer, MenuItemListSerializer, MenuItemDetailSerializer,
    MenuItemCreateUpdateSerializer, RestaurantStatusSerializer, MenuItemStockSerializer,
    NearbyRestaurantFilterSerializer
)
from .permissions import (
    IsRestaurantOwnerOrReadOnly, IsMenuOwnerOrAdmin, CanManageRestaurantStatus,
    CanViewRestaurantReports, IsCustomerForMenuView
)
from apps.accounts.permissions import IsAdminUser, IsCustomerOrAdmin


@extend_schema_view(
    list=extend_schema(summary="لیست رستوران‌ها (با فیلتر نزدیکی)"),
    retrieve=extend_schema(summary="جزییات رستوران"),
    create=extend_schema(summary="ایجاد رستوران جدید (فقط صاحب رستوران)"),
    update=extend_schema(summary="ویرایش کامل رستوران"),
    partial_update=extend_schema(summary="ویرایش جزئی رستوران"),
    destroy=extend_schema(summary="حذف رستوران (فقط ادمین)")
)
class RestaurantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing restaurants
    """
    permission_classes = [IsRestaurantOwnerOrReadOnly]
    filterset_fields = ['cuisine_type', 'is_open', 'is_busy', 'is_verified']
    search_fields = ['name', 'description', 'address']
    
    def get_queryset(self):
        queryset = Restaurant.objects.filter(is_active=True)
        
        # Filter by nearby location if coordinates provided
        lat = self.request.query_params.get('latitude')
        lng = self.request.query_params.get('longitude')
        radius = self.request.query_params.get('radius_km', 5)
        
        if lat and lng:
            # Convert to float
            user_location = (float(lat), float(lng))
            # Annotate with distance
            restaurants_with_distance = []
            for restaurant in queryset:
                rest_location = (float(restaurant.latitude), float(restaurant.longitude))
                dist = distance(user_location, rest_location).kilometers
                if dist <= float(radius):
                    restaurant.distance_km = dist
                    restaurants_with_distance.append(restaurant)
            # Sort by distance
            restaurants_with_distance.sort(key=lambda x: x.distance_km)
            return restaurants_with_distance
        
        # For owners, show their own restaurants first
        if self.request.user.is_restaurant_owner() and not self.request.user.is_admin_user():
            return queryset.filter(owner=self.request.user)
        
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RestaurantListSerializer
        if self.action in ['create', 'update', 'partial_update']:
            return RestaurantCreateUpdateSerializer
        return RestaurantDetailSerializer
    
    @extend_schema(
        parameters=[NearbyRestaurantFilterSerializer],
        summary="رستوران‌های نزدیک به کاربر"
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'], url_path='menu')
    def get_menu(self, request, pk=None):
        """
        Get full menu of a restaurant with categories
        """
        restaurant = self.get_object()
        categories = restaurant.categories.filter(is_active=True)
        
        menu_data = []
        for category in categories:
            items = category.items.filter(is_available=True)
            menu_data.append({
                'category': MenuCategorySerializer(category).data,
                'items': MenuItemListSerializer(items, many=True).data
            })
        
        return Response({
            'restaurant': RestaurantDetailSerializer(restaurant).data,
            'menu': menu_data
        })
    
    @action(detail=True, methods=['post'], url_path='toggle-status', permission_classes=[CanManageRestaurantStatus])
    def toggle_status(self, request, pk=None):
        """
        Toggle restaurant open/closed status
        """
        restaurant = self.get_object()
        restaurant.is_open = not restaurant.is_open
        restaurant.save()
        return Response(RestaurantStatusSerializer(restaurant).data)
    
    @action(detail=True, methods=['get'], url_path='reports', permission_classes=[CanViewRestaurantReports])
    def daily_report(self, request, pk=None):
        """
        Get daily sales report (for restaurant owner)
        """
        restaurant = self.get_object()
        from apps.orders.models import Order
        from django.utils import timezone
        from datetime import timedelta
        
        today = timezone.now().date()
        orders = Order.objects.filter(
            restaurant=restaurant,
            created_at__date=today
        )
        
        total_orders = orders.count()
        completed_orders = orders.filter(status=Order.Status.DELIVERED).count()
        total_revenue = orders.filter(status=Order.Status.DELIVERED).aggregate(
            total=models.Sum('total_amount')
        )['total'] or 0
        
        return Response({
            'restaurant': restaurant.name,
            'date': today,
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'total_revenue': total_revenue,
            'pending_orders': orders.filter(status=Order.Status.PENDING).count(),
            'preparing_orders': orders.filter(status=Order.Status.PREPARING).count(),
            'delivering_orders': orders.filter(status=Order.Status.DELIVERING).count(),
        })


@extend_schema_view(
    list=extend_schema(summary="لیست دسته‌بندی‌های منو"),
    create=extend_schema(summary="ایجاد دسته‌بندی جدید"),
    destroy=extend_schema(summary="حذف دسته‌بندی")
)
class MenuCategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing menu categories
    """
    serializer_class = MenuCategorySerializer
    permission_classes = [IsMenuOwnerOrAdmin]
    
    def get_queryset(self):
        restaurant_id = self.request.query_params.get('restaurant')
        if restaurant_id:
            return MenuCategory.objects.filter(restaurant_id=restaurant_id, is_active=True)
        if self.request.user.is_restaurant_owner():
            return MenuCategory.objects.filter(restaurant__owner=self.request.user)
        return MenuCategory.objects.filter(is_active=True)
    
    def perform_create(self, serializer):
        restaurant_id = self.request.data.get('restaurant')
        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        if not self.request.user.is_admin_user() and restaurant.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("شما اجازه ایجاد دسته برای این رستوران را ندارید.")
        serializer.save(restaurant=restaurant)


@extend_schema_view(
    list=extend_schema(summary="لیست آیتم‌های منو"),
    retrieve=extend_schema(summary="جزییات آیتم منو"),
    create=extend_schema(summary="ایجاد آیتم منو"),
    update=extend_schema(summary="ویرایش آیتم منو"),
    destroy=extend_schema(summary="حذف آیتم منو")
)
class MenuItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing menu items
    """
    permission_classes = [IsCustomerForMenuView]
    filterset_fields = ['category', 'is_available', 'is_featured', 'is_vegetarian']
    search_fields = ['name', 'description']
    
    def get_queryset(self):
        queryset = MenuItem.objects.filter(restaurant__is_active=True)
        
        restaurant_id = self.request.query_params.get('restaurant')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        
        # Only show available items to customers
        if self.request.user.is_customer():
            queryset = queryset.filter(is_available=True, status=MenuItem.ItemStatus.AVAILABLE)
        
        return queryset.select_related('restaurant', 'category')
    
    def get_serializer_class(self):
        if self.action == 'list':
            return MenuItemListSerializer
        if self.action == 'retrieve':
            return MenuItemDetailSerializer
        if self.action == 'update_stock':
            return MenuItemStockSerializer
        return MenuItemCreateUpdateSerializer
    
    def perform_create(self, serializer):
        restaurant_id = self.request.data.get('restaurant')
        restaurant = get_object_or_404(Restaurant, id=restaurant_id)
        if not self.request.user.is_admin_user() and restaurant.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("شما اجازه اضافه کردن آیتم به این رستوران را ندارید.")
        serializer.save(restaurant=restaurant)
    
    @action(detail=True, methods=['patch'], url_path='stock', permission_classes=[IsMenuOwnerOrAdmin])
    def update_stock(self, request, pk=None):
        """
        Update menu item stock
        """
        menu_item = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        menu_item.stock = serializer.validated_data['stock']
        menu_item.is_available = menu_item.stock > 0
        menu_item.save()
        return Response(MenuItemDetailSerializer(menu_item).data)
    