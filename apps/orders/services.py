"""
Order services with concurrency management using select_for_update()
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import F, Q
from typing import Dict, Any, Optional, Tuple
import logging

from .models import Order, OrderItem, Cart
from apps.restaurants.models import MenuItem, Restaurant

logger = logging.getLogger(__name__)


class OrderCreationService:
    """
    Service for creating orders with proper locking to prevent concurrency issues
    """
    
    @classmethod
    @transaction.atomic
    def create_order_with_lock(cls, user, validated_data: Dict[str, Any]) -> Order:
        """
        Create an order with select_for_update locks to prevent race conditions.
        
        Locks acquired:
        1. Cart items with select_for_update
        2. Menu items with select_for_update (for stock validation)
        3. Restaurant with select_for_update (for concurrent order count)
        
        Returns:
            Order: The created order object
            
        Raises:
            ValidationError: If stock is insufficient or restaurant is busy
        """
        
        restaurant = validated_data['restaurant']
        
        # Lock 1: Lock the restaurant to prevent order count race condition
        restaurant_locked = Restaurant.objects.select_for_update().filter(
            id=restaurant.id, is_active=True
        ).first()
        
        if not restaurant_locked:
            raise ValidationError({"restaurant": "رستوران مورد نظر فعال نیست."})
        
        # Check if restaurant can accept new order (with locked data)
        if not restaurant_locked.can_accept_new_order():
            raise ValidationError({"restaurant": "رستوران در حال حاضر قادر به پذیرش سفارش جدید نیست."})
        
        # Lock 2: Get user's cart and lock its items
        try:
            cart = Cart.objects.select_for_update().get(customer=user)
        except Cart.DoesNotExist:
            raise ValidationError({"cart": "سبد خرید یافت نشد."})
        
        # Lock 3: Lock all cart items
        cart_items = list(cart.items.select_for_update().select_related('menu_item'))
        
        if not cart_items:
            raise ValidationError({"cart": "سبد خرید شما خالی است."})
        
        # Lock 4: Lock all menu items that are in cart (prevent stock race)
        menu_item_ids = [item.menu_item_id for item in cart_items]
        menu_items_locked = MenuItem.objects.select_for_update().filter(
            id__in=menu_item_ids
        )
        menu_items_dict = {item.id: item for item in menu_items_locked}
        
        # Validate all items belong to same restaurant and have sufficient stock
        subtotal = 0
        order_items_data = []
        
        for cart_item in cart_items:
            menu_item = menu_items_dict.get(cart_item.menu_item_id)
            
            if not menu_item:
                raise ValidationError({"menu_item": f"آیتم {cart_item.menu_item.name} یافت نشد."})
            
            if menu_item.restaurant_id != restaurant.id:
                raise ValidationError({
                    "restaurant": "همه آیتم‌های سبد خرید باید از یک رستوران باشند."
                })
            
            if not menu_item.is_available:
                raise ValidationError({
                    "menu_item": f"آیتم {menu_item.name} در حال حاضر موجود نیست."
                })
            
            if menu_item.stock < cart_item.quantity:
                raise ValidationError({
                    "menu_item": f"موجودی {menu_item.name} کافی نیست. (موجودی: {menu_item.stock})"
                })
            
            # Calculate item total
            item_total = menu_item.price * cart_item.quantity
            subtotal += item_total
            
            order_items_data.append({
                'menu_item': menu_item,
                'cart_item': cart_item,
                'quantity': cart_item.quantity,
                'price': menu_item.price,
                'total': item_total
            })
        
        # Calculate delivery fee (from serializer validation)
        delivery_fee = validated_data.get('delivery_fee', 0)
        
        # Calculate total amount
        total_amount = subtotal + delivery_fee - validated_data.get('discount', 0)
        
        # Create the order
        order = Order.objects.create(
            customer=user,
            restaurant=restaurant_locked,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            discount=validated_data.get('discount', 0),
            total_amount=total_amount,
            delivery_address=validated_data['delivery_address'],
            customer_latitude=validated_data['customer_latitude'],
            customer_longitude=validated_data['customer_longitude'],
            payment_method=validated_data.get('payment_method', Order.PaymentMethod.CASH),
            customer_note=validated_data.get('customer_note', ''),
            distance_km=validated_data.get('distance_km', 0),
            estimated_delivery_time=timezone.now() + timezone.timedelta(minutes=restaurant_locked.delivery_time)
        )
        
        # Create order items and deduct stock (still within atomic transaction)
        for item_data in order_items_data:
            menu_item = item_data['menu_item']
            cart_item = item_data['cart_item']
            
            OrderItem.objects.create(
                order=order,
                menu_item=menu_item,
                quantity=item_data['quantity'],
                price=item_data['price'],
                total=item_data['total'],
                item_name=menu_item.name,
                item_description=menu_item.description
            )
            
            # Deduct stock (we have lock, so safe)
            menu_item.stock -= item_data['quantity']
            if menu_item.stock == 0:
                menu_item.is_available = False
                menu_item.status = MenuItem.ItemStatus.UNAVAILABLE
            menu_item.save(update_fields=['stock', 'is_available', 'status'])
        
        # Increment restaurant order count
        restaurant_locked.current_orders_count = F('current_orders_count') + 1
        restaurant_locked.save(update_fields=['current_orders_count'])
        
        # Check if restaurant is now busy and update
        restaurant_locked.refresh_from_db()
        if restaurant_locked.current_orders_count >= restaurant_locked.max_concurrent_orders:
            restaurant_locked.is_busy = True
            restaurant_locked.save(update_fields=['is_busy'])
        
        # Clear the cart (still within locked transaction)
        cart.items.all().delete()
        
        logger.info(f"Order {order.order_number} created successfully by user {user.id}")
        
        return order


class OrderAssignmentService:
    """
    Service for assigning orders to delivery riders with concurrency control
    """
    
    @classmethod
    @transaction.atomic
    def assign_rider_to_order(cls, order_id: int, rider_id: int) -> Optional[Order]:
        """
        Assign a rider to an order with proper locking.
        Prevents multiple riders from accepting the same order.
        
        Args:
            order_id: The order ID to assign
            rider_id: The rider user ID
            
        Returns:
            Order: The updated order if assignment successful, None otherwise
        """
        from apps.accounts.models import User
        
        # Lock both order and rider simultaneously
        try:
            # Lock order with select_for_update (skip locked for timeout)
            order = Order.objects.select_for_update(nowait=True).filter(
                id=order_id,
                status=Order.Status.READY,  # Only orders ready for pickup
                rider__isnull=True  # Not yet assigned
            ).first()
            
            if not order:
                logger.warning(f"Order {order_id} is not available for assignment")
                return None
            
            # Lock rider with select_for_update
            rider = User.objects.select_for_update(nowait=True).filter(
                id=rider_id,
                role=User.Role.DELIVERY_RIDER,
                is_active=True,
                rider_status=User.RiderStatus.AVAILABLE
            ).first()
            
            if not rider:
                logger.warning(f"Rider {rider_id} is not available")
                return None
            
            # Assign order to rider
            order.rider = rider
            order.status = Order.Status.DELIVERING
            order.save(update_fields=['rider', 'status'])
            
            # Update rider status to busy
            rider.rider_status = User.RiderStatus.BUSY
            rider.save(update_fields=['rider_status'])
            
            logger.info(f"Order {order.order_number} assigned to rider {rider_id}")
            
            # Trigger async notification (Celery task)
            cls._send_assignment_notification.delay(order.id, rider.id)
            
            return order
            
        except Exception as e:
            logger.error(f"Failed to assign order {order_id} to rider {rider_id}: {e}")
            return None
    
    @staticmethod
    def _send_assignment_notification(order_id: int, rider_id: int):
        """
        Placeholder for Celery task to send push notification
        """
        # This will be implemented with Celery later
        pass


class OrderCancellationService:
    """
    Service for cancelling orders with stock restoration
    """
    
    @classmethod
    @transaction.atomic
    def cancel_order_with_lock(cls, order_id: int, user) -> Tuple[bool, str]:
        """
        Cancel an order with select_for_update lock and restore stock.
        
        Args:
            order_id: The order ID to cancel
            user: The user requesting cancellation
            
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            # Lock the order
            order = Order.objects.select_for_update(nowait=True).filter(
                id=order_id
            ).first()
            
            if not order:
                return False, "سفارش یافت نشد."
            
            # Check permission
            if order.customer != user and not user.is_admin_user():
                return False, "شما اجازه لغو این سفارش را ندارید."
            
            # Check if order can be cancelled
            if not order.can_cancel():
                return False, f"سفارش در وضعیت {order.get_status_display()} قابل لغو نیست."
            
            # Lock and restore stock for all order items
            order_items = OrderItem.objects.select_for_update().filter(
                order=order
            ).select_related('menu_item')
            
            for order_item in order_items:
                menu_item = order_item.menu_item
                menu_item.stock += order_item.quantity
                if menu_item.stock > 0:
                    menu_item.is_available = True
                    menu_item.status = MenuItem.ItemStatus.AVAILABLE
                menu_item.save(update_fields=['stock', 'is_available', 'status'])
            
            # Lock restaurant and decrement order count
            restaurant = Restaurant.objects.select_for_update().filter(
                id=order.restaurant_id
            ).first()
            
            if restaurant:
                restaurant.current_orders_count = F('current_orders_count') - 1
                restaurant.save(update_fields=['current_orders_count'])
                restaurant.refresh_from_db()
                if restaurant.current_orders_count < restaurant.max_concurrent_orders:
                    restaurant.is_busy = False
                    restaurant.save(update_fields=['is_busy'])
            
            # If rider was assigned, free them
            if order.rider:
                rider = User.objects.select_for_update().filter(
                    id=order.rider_id
                ).first()
                if rider:
                    rider.rider_status = User.RiderStatus.AVAILABLE
                    rider.save(update_fields=['rider_status'])
            
            # Cancel the order
            order.status = Order.Status.CANCELLED
            order.cancelled_at = timezone.now()
            order.save(update_fields=['status', 'cancelled_at'])
            
            logger.info(f"Order {order.order_number} cancelled by user {user.id}")
            
            return True, "سفارش با موفقیت لغو شد."
            
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False, "خطا در لغو سفارش. لطفاً مجدد تلاش کنید."


def get_available_orders_for_rider(rider_location: Tuple[float, float], radius_km: int = 5):
    """
    Get orders that are available for delivery and near the rider.
    This does NOT require a database lock (read-only operation).
    """
    from geopy.distance import distance
    
    ready_orders = Order.objects.filter(
        status=Order.Status.READY,
        rider__isnull=True,
        restaurant__is_open=True
    ).select_related('restaurant', 'customer')
    
    available_orders = []
    for order in ready_orders:
        restaurant_location = order.restaurant.get_location()
        dist = distance(rider_location, restaurant_location).kilometers
        if dist <= radius_km:
            order.distance_to_rider = round(dist, 2)
            available_orders.append(order)
    
    # Sort by distance
    available_orders.sort(key=lambda x: x.distance_to_rider)
    
    return available_orders