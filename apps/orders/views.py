from rest_framework import generics, viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db import transaction
from geopy.distance import distance
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Order, Cart, CartItem, OrderItem
from .serializers import (
    CartSerializer, AddToCartSerializer, OrderListSerializer, OrderDetailSerializer,
    OrderCreateSerializer, OrderStatusUpdateSerializer, OrderAssignSerializer,
    CalculateDeliveryFeeSerializer, CartItemSerializer
)
from .services import (
    OrderCreationService, OrderAssignmentService, 
    OrderCancellationService, get_available_orders_for_rider
)
from apps.accounts.permissions import IsCustomer, IsDeliveryRider, IsRestaurantOwner, IsAdminUser
from apps.restaurants.models import MenuItem


class CartViewSet(viewsets.GenericViewSet):
    """
    Shopping cart management
    """
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = CartSerializer
    
    def get_queryset(self):
        return Cart.objects.filter(customer=self.request.user)
    
    @extend_schema(summary="مشاهده سبد خرید")
    def list(self, request):
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        serializer = self.get_serializer(cart)
        return Response(serializer.data)
    
    @extend_schema(
        request=AddToCartSerializer,
        summary="افزودن آیتم به سبد خرید"
    )
    @action(detail=False, methods=['post'], url_path='add')
    def add_item(self, request):
        serializer = AddToCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        menu_item = get_object_or_404(MenuItem, id=serializer.validated_data['menu_item_id'])
        
        if not menu_item.is_available:
            return Response(
                {"error": "این آیتم در حال حاضر موجود نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        
        # Check if item already in cart
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=menu_item,
            defaults={'quantity': serializer.validated_data['quantity']}
        )
        
        if not created:
            cart_item.quantity += serializer.validated_data['quantity']
            cart_item.save()
        
        return Response(CartSerializer(cart).data, status=status.HTTP_200_OK)
    
    @extend_schema(summary="حذف آیتم از سبد خرید")
    @action(detail=False, methods=['delete'], url_path='remove/(?P<item_id>[^/.]+)')
    def remove_item(self, request, item_id=None):
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        cart_item.delete()
        return Response(CartSerializer(cart).data)
    
    @extend_schema(summary="بروزرسانی تعداد آیتم در سبد خرید")
    @action(detail=False, methods=['patch'], url_path='update/(?P<item_id>[^/.]+)')
    def update_quantity(self, request, item_id=None):
        quantity = request.data.get('quantity')
        if not quantity or quantity < 1:
            return Response(
                {"quantity": "تعداد باید حداقل 1 باشد."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        cart_item.quantity = quantity
        cart_item.save()
        
        return Response(CartSerializer(cart).data)
    
    @extend_schema(summary="خالی کردن سبد خرید")
    @action(detail=False, methods=['delete'], url_path='clear')
    def clear_cart(self, request):
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        cart.items.all().delete()
        return Response({"message": "سبد خرید خالی شد."})


@extend_schema_view(
    list=extend_schema(summary="لیست سفارش‌های کاربر"),
    retrieve=extend_schema(summary="جزییات سفارش"),
    create=extend_schema(summary="ثبت سفارش جدید"),
)
class OrderViewSet(viewsets.GenericViewSet):
    """
    Order management
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user():
            return Order.objects.all()
        elif user.is_restaurant_owner():
            return Order.objects.filter(restaurant__owner=user)
        elif user.is_delivery_rider():
            return Order.objects.filter(rider=user)
        else:  # Customer
            return Order.objects.filter(customer=user)
    
    def get_serializer_class(self):
        if self.action == 'list':
            return OrderListSerializer
        elif self.action == 'retrieve':
            return OrderDetailSerializer
        elif self.action == 'create':
            return OrderCreateSerializer
        return OrderDetailSerializer
    
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        order = get_object_or_404(self.get_queryset(), id=pk)
        serializer = self.get_serializer(order)
        return Response(serializer.data)
    
    @extend_schema(
        request=OrderCreateSerializer,
        summary="ثبت سفارش جدید (با قفل روی موجودی)"
    )
    def create(self, request):
        serializer = OrderCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Ensure user has a cart
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        if not cart.items.exists():
            return Response(
                {"error": "سبد خرید شما خالی است."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate delivery fee
        restaurant = serializer.validated_data['restaurant']
        restaurant_location = restaurant.get_location()
        customer_location = (
            float(serializer.validated_data['customer_latitude']),
            float(serializer.validated_data['customer_longitude'])
        )
        dist_km = distance(restaurant_location, customer_location).kilometers
        
        from config.settings.base import DELIVERY_BASE_FEE, DELIVERY_FEE_PER_KM
        delivery_fee = DELIVERY_BASE_FEE + (dist_km * DELIVERY_FEE_PER_KM)
        
        validated_data = serializer.validated_data
        validated_data['delivery_fee'] = delivery_fee
        validated_data['distance_km'] = dist_km
        
        try:
            order = OrderCreationService.create_order_with_lock(request.user, validated_data)
            return Response(
                OrderDetailSerializer(order).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @extend_schema(
        request=OrderStatusUpdateSerializer,
        summary="بروزرسانی وضعیت سفارش"
    )
    @action(detail=True, methods=['patch'], url_path='status')
    def update_status(self, request, pk=None):
        order = get_object_or_404(self.get_queryset(), id=pk)
        
        # Permission check
        user = request.user
        if not (user.is_admin_user() or 
                (user.is_restaurant_owner() and order.restaurant.owner == user) or
                (user.is_delivery_rider() and order.rider == user)):
            return Response(
                {"error": "شما اجازه تغییر وضعیت این سفارش را ندارید."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = OrderStatusUpdateSerializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        order.update_status(serializer.validated_data['status'])
        
        return Response(OrderDetailSerializer(order).data)
    
    @extend_schema(summary="لغو سفارش (با بازگرداندن موجودی)")
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel_order(self, request, pk=None):
        success, message = OrderCancellationService.cancel_order_with_lock(pk, request.user)
        
        if success:
            return Response({"message": message}, status=status.HTTP_200_OK)
        return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)
    
    @extend_schema(summary="سفارش‌های آماده برای تحویل (برای راننده)")
    @action(detail=False, methods=['get'], url_path='available')
    def available_orders(self, request):
        """Get orders ready for delivery (for riders)"""
        if not request.user.is_delivery_rider() and not request.user.is_admin_user():
            return Response(
                {"error": "فقط رانندگان می‌توانند این لیست را ببینند."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        rider_location = request.user.get_location()
        if not rider_location:
            return Response(
                {"error": "لطفاً ابتدا موقعیت خود را ثبت کنید."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        radius = request.query_params.get('radius_km', 5)
        available_orders = get_available_orders_for_rider(rider_location, int(radius))
        
        serializer = OrderListSerializer(available_orders, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        request=OrderAssignSerializer,
        summary="قبول سفارش توسط راننده (با قفل همزمانی)"
    )
    @action(detail=True, methods=['post'], url_path='accept')
    def accept_order(self, request, pk=None):
        """Rider accepts an order for delivery"""
        if not request.user.is_delivery_rider():
            return Response(
                {"error": "فقط رانندگان می‌توانند سفارش قبول کنند."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        order = get_object_or_404(Order, id=pk)
        
        if order.status != Order.Status.READY:
            return Response(
                {"error": f"این سفارش در وضعیت {order.get_status_display()} قابل قبول نیست."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if order.rider:
            return Response(
                {"error": "این سفارش قبلاً توسط راننده دیگری قبول شده است."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        assigned_order = OrderAssignmentService.assign_rider_to_order(pk, request.user.id)
        
        if assigned_order:
            return Response(OrderDetailSerializer(assigned_order).data)
        
        return Response(
            {"error": "امکان قبول این سفارش وجود ندارد."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @extend_schema(summary="محاسبه هزینه ارسال")
    @action(detail=False, methods=['post'], url_path='calculate-delivery-fee')
    def calculate_delivery_fee(self, request):
        serializer = CalculateDeliveryFeeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        restaurant = serializer.validated_data['restaurant_id']
        restaurant = get_object_or_404(Restaurant, id=restaurant.id)
        
        restaurant_location = restaurant.get_location()
        customer_location = (
            float(serializer.validated_data['customer_latitude']),
            float(serializer.validated_data['customer_longitude'])
        )
        
        dist_km = distance(restaurant_location, customer_location).kilometers
        
        from config.settings.base import DELIVERY_BASE_FEE, DELIVERY_FEE_PER_KM
        delivery_fee = DELIVERY_BASE_FEE + (dist_km * DELIVERY_FEE_PER_KM)
        
        return Response({
            'distance_km': round(dist_km, 2),
            'delivery_fee': round(delivery_fee),
            'base_fee': DELIVERY_BASE_FEE,
            'fee_per_km': DELIVERY_FEE_PER_KM
        })