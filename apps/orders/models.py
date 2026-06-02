from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from apps.accounts.models import User
from apps.restaurants.models import Restaurant, MenuItem


class Order(models.Model):
    """
    Main Order model for food delivery system
    """
    class Status(models.TextChoices):
        PENDING = 'pending', 'در انتظار تایید'
        CONFIRMED = 'confirmed', 'تایید شده'
        PREPARING = 'preparing', 'در حال آماده‌سازی'
        READY = 'ready', 'آماده تحویل'
        DELIVERING = 'delivering', 'در مسیر تحویل'
        DELIVERED = 'delivered', 'تحویل داده شده'
        CANCELLED = 'cancelled', 'لغو شده'
        REJECTED = 'rejected', 'رد شده'

    class PaymentMethod(models.TextChoices):
        CASH = 'cash', 'نقدی'
        CARD = 'card', 'کارت بانکی'
        ONLINE = 'online', 'آنلاین'

    # Relationships
    customer = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='orders',
        limit_choices_to={'role': User.Role.CUSTOMER}
    )
    restaurant = models.ForeignKey(
        Restaurant, 
        on_delete=models.CASCADE, 
        related_name='orders'
    )
    rider = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='delivery_orders',
        limit_choices_to={'role': User.Role.DELIVERY_RIDER}
    )

    # Order details
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    subtotal = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='جمع سفارش')
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name='هزینه ارسال')
    discount = models.DecimalField(max_digits=10, decimal_places=0, default=0, verbose_name='تخفیف')
    total_amount = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='قابل پرداخت')
    
    # Address
    delivery_address = models.TextField(verbose_name='آدرس تحویل')
    customer_latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='طول جغرافیایی مشتری')
    customer_longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='عرض جغرافیایی مشتری')
    
    # Status
    status = models.CharField(
        max_length=20, 
        choices=Status.choices, 
        default=Status.PENDING,
        verbose_name='وضعیت'
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name='روش پرداخت'
    )
    is_paid = models.BooleanField(default=False, verbose_name='پرداخت شده')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Delivery info
    estimated_delivery_time = models.DateTimeField(null=True, blank=True, verbose_name='زمان تخمینی تحویل')
    distance_km = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='مسافت برحسب کیلومتر')
    preparation_time = models.PositiveIntegerField(default=0, help_text='زمان آماده‌سازی به دقیقه')
    
    # Notes
    customer_note = models.TextField(blank=True, verbose_name='یادداشت مشتری')
    rider_note = models.TextField(blank=True, verbose_name='یادداشت راننده')
    
    class Meta:
        verbose_name = 'سفارش'
        verbose_name_plural = 'سفارش‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['restaurant', 'status']),
            models.Index(fields=['rider', 'status']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['order_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"سفارش #{self.order_number} - {self.customer.get_full_name()}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)
    
    def generate_order_number(self):
        """Generate unique order number: DNF + YYMMDD + random 4 digits"""
        import random
        date_part = timezone.now().strftime('%y%m%d')
        random_part = str(random.randint(1000, 9999))
        return f"DNF{date_part}{random_part}"
    
    def can_cancel(self):
        """Check if order can be cancelled"""
        return self.status in [self.Status.PENDING, self.Status.CONFIRMED]
    
    def cancel(self):
        """Cancel order and restore stock"""
        if self.can_cancel():
            self.status = self.Status.CANCELLED
            self.cancelled_at = timezone.now()
            # Restore stock for all items
            for item in self.items.all():
                item.menu_item.stock += item.quantity
                item.menu_item.save()
            self.save()
            return True
        return False
    
    def update_status(self, new_status):
        """Update order status with timestamp tracking"""
        self.status = new_status
        
        if new_status == self.Status.CONFIRMED and not self.confirmed_at:
            self.confirmed_at = timezone.now()
        elif new_status == self.Status.READY and not self.ready_at:
            self.ready_at = timezone.now()
        elif new_status == self.Status.DELIVERED and not self.delivered_at:
            self.delivered_at = timezone.now()
        
        self.save()


class OrderItem(models.Model):
    """
    Individual items within an order
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='قیمت واحد')
    total = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='جمع')
    
    # Snapshot of item details at order time
    item_name = models.CharField(max_length=255, verbose_name='نام آیتم')
    item_description = models.TextField(blank=True, verbose_name='توضیحات آیتم')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'آیتم سفارش'
        verbose_name_plural = 'آیتم‌های سفارش'
    
    def __str__(self):
        return f"{self.quantity}x {self.item_name} - سفارش #{self.order.order_number}"
    
    def save(self, *args, **kwargs):
        self.total = self.price * self.quantity
        super().save(*args, **kwargs)


class Cart(models.Model):
    """
    Shopping cart for customers before checkout
    """
    customer = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='cart',
        limit_choices_to={'role': User.Role.CUSTOMER}
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'سبد خرید'
        verbose_name_plural = 'سبدهای خرید'
    
    def __str__(self):
        return f"سبد خرید {self.customer.get_full_name()}"
    
    @property
    def total(self):
        return sum(item.total for item in self.items.all())
    
    @property
    def items_count(self):
        return self.items.count()
    
    def clear(self):
        self.items.all().delete()


class CartItem(models.Model):
    """
    Individual items in shopping cart
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'آیتم سبد خرید'
        verbose_name_plural = 'آیتم‌های سبد خرید'
        unique_together = ['cart', 'menu_item']
    
    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name}"
    
    @property
    def total(self):
        return self.menu_item.price * self.quantity
    
    