from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from geopy.distance import distance

from .models import Order, OrderItem, Cart, CartItem
from apps.restaurants.models import MenuItem, Restaurant
from apps.accounts.serializers import UserSerializer
from config.settings.base import DELIVERY_BASE_FEE, DELIVERY_FEE_PER_KM, PEAK_TIME_START, PEAK_TIME_END, PEAK_TIME_MULTIPLIER


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer for cart items
    """
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    menu_item_price = serializers.DecimalField(source='menu_item.price', read_only=True, max_digits=10, decimal_places=0)
    menu_item_image = serializers.ImageField(source='menu_item.image', read_only=True)
    total = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=0)
    
    class Meta:
        model = CartItem
        fields = ['id', 'menu_item', 'menu_item_name', 'menu_item_price', 'menu_item_image', 'quantity', 'total']
        read_only_fields = ['id']


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for shopping cart
    """
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(read_only=True, max_digits=10, decimal_places=0)
    items_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Cart
        fields = ['id', 'items', 'total', 'items_count', 'created_at', 'updated_at']


class AddToCartSerializer(serializers.Serializer):
    """
    Serializer for adding item to cart
    """
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)
    
    def validate_menu_item_id(self, value):
        try:
            menu_item = MenuItem.objects.select_related('restaurant').get(id=value)
            if not menu_item.is_available:
                raise serializers.ValidationError("این آیتم در حال حاضر موجود نیست.")
            return value
        except MenuItem.DoesNotExist:
            raise serializers.ValidationError("آیتم مورد نظر یافت نشد.")


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for order items
    """
    menu_item_name = serializers.CharField(source='item_name', read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'menu_item', 'menu_item_name', 'quantity', 'price', 'total']


class OrderListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing orders
    """
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    customer_name = serializers.SerializerMethodField()
    rider_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'restaurant', 'restaurant_name', 'customer_name',
            'rider_name', 'total_amount', 'status', 'status_display',
            'created_at', 'estimated_delivery_time'
        ]
    
    def get_customer_name(self, obj):
        return obj.customer.get_full_name() or obj.customer.username
    
    def get_rider_name(self, obj):
        if obj.rider:
            return obj.rider.get_full_name() or obj.rider.username
        return None


class OrderDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single order
    """
    items = OrderItemSerializer(many=True, read_only=True)
    customer = UserSerializer(read_only=True)
    rider = UserSerializer(read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    restaurant_address = serializers.CharField(source='restaurant.address', read_only=True)
    restaurant_phone = serializers.CharField(source='restaurant.phone_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'customer', 'restaurant', 'restaurant_name',
            'restaurant_address', 'restaurant_phone', 'rider', 'items',
            'subtotal', 'delivery_fee', 'discount', 'total_amount',
            'delivery_address', 'customer_latitude', 'customer_longitude',
            'status', 'status_display', 'payment_method', 'payment_method_display',
            'is_paid', 'created_at', 'confirmed_at', 'ready_at', 'delivered_at',
            'estimated_delivery_time', 'distance_km', 'customer_note', 'rider_note'
        ]
        read_only_fields = ['id', 'order_number', 'created_at']


class CalculateDeliveryFeeSerializer(serializers.Serializer):
    """
    Serializer for calculating delivery fee
    """
    restaurant_id = serializers.IntegerField()
    customer_latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    customer_longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    
    def validate_restaurant_id(self, value):
        try:
            restaurant = Restaurant.objects.get(id=value, is_active=True)
            if not restaurant.is_open:
                raise serializers.ValidationError("این رستوران در حال حاضر بسته است.")
            return value
        except Restaurant.DoesNotExist:
            raise serializers.ValidationError("رستوران مورد نظر یافت نشد.")


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new order with lock on menu items
    """
    customer_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    customer_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    delivery_address = serializers.CharField(required=True)
    payment_method = serializers.ChoiceField(choices=Order.PaymentMethod.choices, default=Order.PaymentMethod.CASH)
    customer_note = serializers.CharField(required=False, allow_blank=True)
    
    class Meta:
        model = Order
        fields = [
            'restaurant', 'customer_latitude', 'customer_longitude',
            'delivery_address', 'payment_method', 'customer_note'
        ]
    
    def validate_restaurant(self, value):
        if not value.can_accept_new_order():
            raise serializers.ValidationError("این رستوران در حال حاضر قادر به پذیرش سفارش جدید نیست.")
        return value
    
    def create(self, validated_data):
        user = self.context['request'].user
        restaurant = validated_data['restaurant']
        
        # Get user's cart
        cart = Cart.objects.get(customer=user)
        if not cart.items.exists():
            raise serializers.ValidationError({"cart": "سبد خرید شما خالی است."})
        
        # Check all items are available and from same restaurant
        for cart_item in cart.items.all():
            if cart_item.menu_item.restaurant != restaurant:
                raise serializers.ValidationError(
                    {"restaurant": "همه آیتم‌های سبد خرید باید از یک رستوران باشند."}
                )
            if not cart_item.menu_item.is_available or cart_item.menu_item.stock < cart_item.quantity:
                raise serializers.ValidationError(
                    {"menu_item": f"آیتم {cart_item.menu_item.name} به تعداد کافی موجود نیست."}
                )
        
        # Calculate subtotal
        subtotal = cart.total
        
        # Calculate distance and delivery fee
        restaurant_location = restaurant.get_location()
        customer_location = (float(validated_data['customer_latitude']), float(validated_data['customer_longitude']))
        dist_km = distance(restaurant_location, customer_location).kilometers
        
        delivery_fee = self.calculate_delivery_fee(dist_km)
        
        # Calculate total
        total = subtotal + delivery_fee
        
        # Create order with atomic transaction (using select_for_update later in service)
        order = Order.objects.create(
            customer=user,
            restaurant=restaurant,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount=0,
            total_amount=total,
            delivery_address=validated_data['delivery_address'],
            customer_latitude=validated_data['customer_latitude'],
            customer_longitude=validated_data['customer_longitude'],
            payment_method=validated_data['payment_method'],
            customer_note=validated_data.get('customer_note', ''),
            distance_km=dist_km,
            estimated_delivery_time=timezone.now() + timezone.timedelta(minutes=restaurant.delivery_time)
        )
        
        # Create order items and deduct stock
        for cart_item in cart.items.all():
            OrderItem.objects.create(
                order=order,
                menu_item=cart_item.menu_item,
                quantity=cart_item.quantity,
                price=cart_item.menu_item.price,
                item_name=cart_item.menu_item.name,
                item_description=cart_item.menu_item.description
            )
            # Deduct stock
            cart_item.menu_item.deduct_stock(cart_item.quantity)
        
        # Increment restaurant order count
        restaurant.increment_order_count()
        
        # Clear cart
        cart.clear()
        
        return order
    
    def calculate_delivery_fee(self, distance_km):
        """
        Calculate delivery fee based on distance and peak time
        """
        fee = DELIVERY_BASE_FEE + (distance_km * DELIVERY_FEE_PER_KM)
        
        # Peak time multiplier
        current_hour = timezone.now().hour
        if PEAK_TIME_START <= current_hour < PEAK_TIME_END:
            fee = fee * PEAK_TIME_MULTIPLIER
        
        return round(fee)


class OrderStatusUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating order status
    """
    class Meta:
        model = Order
        fields = ['status']
    
    def validate_status(self, value):
        order = self.instance
        valid_transitions = {
            Order.Status.PENDING: [Order.Status.CONFIRMED, Order.Status.CANCELLED, Order.Status.REJECTED],
            Order.Status.CONFIRMED: [Order.Status.PREPARING, Order.Status.CANCELLED],
            Order.Status.PREPARING: [Order.Status.READY],
            Order.Status.READY: [Order.Status.DELIVERING],
            Order.Status.DELIVERING: [Order.Status.DELIVERED],
        }
        
        if order.status in valid_transitions and value not in valid_transitions[order.status]:
            raise serializers.ValidationError(f"امکان تغییر وضعیت از {order.get_status_display()} به {dict(Order.Status.choices)[value]} وجود ندارد.")
        
        return value


class OrderAssignSerializer(serializers.Serializer):
    """
    Serializer for assigning rider to order
    """
    rider_id = serializers.IntegerField(required=False)
    
    def validate_rider_id(self, value):
        from apps.accounts.models import User
        try:
            rider = User.objects.get(id=value, role=User.Role.DELIVERY_RIDER, is_active=True)
            if rider.rider_status != User.RiderStatus.AVAILABLE:
                raise serializers.ValidationError("این راننده در حال حاضر در دسترس نیست.")
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("راننده مورد نظر یافت نشد.")
        