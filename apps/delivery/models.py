from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.accounts.models import User
from apps.orders.models import Order


class DeliveryTracking(models.Model):
    """
    Real-time tracking for each delivery
    """
    class TrackingStatus(models.TextChoices):
        PENDING = 'pending', 'در انتظار'
        PICKUP = 'pickup', 'در مسیر رستوران'
        AT_RESTAURANT = 'at_restaurant', 'رسیده به رستوران'
        PICKED_UP = 'picked_up', 'تحویل گرفته شد'
        DELIVERING = 'delivering', 'در مسیر مشتری'
        DELIVERED = 'delivered', 'تحویل داده شد'
        FAILED = 'failed', 'ناموفق'

    order = models.OneToOneField(
        Order, 
        on_delete=models.CASCADE, 
        related_name='tracking',
        limit_choices_to={'status__in': [Order.Status.DELIVERING, Order.Status.DELIVERED]}
    )
    rider = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='delivery_trackings',
        limit_choices_to={'role': User.Role.DELIVERY_RIDER}
    )
    
    status = models.CharField(
        max_length=20,
        choices=TrackingStatus.choices,
        default=TrackingStatus.PENDING,
        verbose_name='وضعیت تحویل'
    )
    
    # Timestamps for each milestone
    assigned_at = models.DateTimeField(auto_now_add=True)
    pickup_started_at = models.DateTimeField(null=True, blank=True)
    arrived_at_restaurant = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Location tracking (snapshots)
    restaurant_arrival_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    restaurant_arrival_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    delivery_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Performance metrics
    distance_traveled_km = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    time_to_restaurant_minutes = models.PositiveIntegerField(null=True, blank=True)
    time_to_delivery_minutes = models.PositiveIntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'ردیابی تحویل'
        verbose_name_plural = 'ردیابی‌های تحویل'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['rider', 'status']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"Track {self.order.order_number} - {self.get_status_display()}"

    def update_status(self, new_status, latitude=None, longitude=None):
        """
        Update delivery status with automatic timestamp and location tracking
        """
        self.status = new_status
        
        # Auto-set timestamps based on status
        if new_status == self.TrackingStatus.PICKUP and not self.pickup_started_at:
            self.pickup_started_at = timezone.now()
        elif new_status == self.TrackingStatus.AT_RESTAURANT and not self.arrived_at_restaurant:
            self.arrived_at_restaurant = timezone.now()
            if latitude and longitude:
                self.restaurant_arrival_latitude = latitude
                self.restaurant_arrival_longitude = longitude
        elif new_status == self.TrackingStatus.PICKED_UP and not self.picked_up_at:
            self.picked_up_at = timezone.now()
            if latitude and longitude:
                self.pickup_latitude = latitude
                self.pickup_longitude = longitude
            # Calculate time to restaurant
            if self.arrived_at_restaurant:
                self.time_to_restaurant_minutes = int(
                    (self.picked_up_at - self.arrived_at_restaurant).total_seconds() / 60
                )
        elif new_status == self.TrackingStatus.DELIVERED and not self.delivered_at:
            self.delivered_at = timezone.now()
            if latitude and longitude:
                self.delivery_latitude = latitude
                self.delivery_longitude = longitude
            # Calculate total delivery time
            if self.picked_up_at:
                self.time_to_delivery_minutes = int(
                    (self.delivered_at - self.picked_up_at).total_seconds() / 60
                )
        
        self.save()


class RiderLocationHistory(models.Model):
    """
    Historical record of rider locations for analytics and replay
    """
    rider = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='location_history',
        limit_choices_to={'role': User.Role.DELIVERY_RIDER}
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    speed_kmh = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    bearing = models.IntegerField(null=True, blank=True, help_text='جهت حرکت بر حسب درجه')
    
    # Which order was the rider working on (if any)
    active_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'تاریخچه موقعیت راننده'
        verbose_name_plural = 'تاریخچه موقعیت رانندگان'
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['rider', '-recorded_at']),
            models.Index(fields=['recorded_at']),
        ]

    def __str__(self):
        return f"{self.rider.get_full_name()} - {self.recorded_at}"


class DeliveryZone(models.Model):
    """
    Delivery zones for dynamic pricing and availability
    """
    name = models.CharField(max_length=100, verbose_name='نام منطقه')
    center_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    center_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    radius_km = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    
    # Additional delivery fee for this zone
    extra_fee = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'منطقه تحویل'
        verbose_name_plural = 'مناطق تحویل'
    
    def __str__(self):
        return f"{self.name} (+{self.extra_fee} تومان)"


class PeakTimeSetting(models.Model):
    """
    Dynamic peak time pricing settings
    """
    day_of_week = models.IntegerField(
        choices=[(i, ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه'][i]) for i in range(7)],
        verbose_name='روز هفته'
    )
    start_hour = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(23)])
    end_hour = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(23)])
    multiplier = models.DecimalField(max_digits=3, decimal_places=2, default=1.5)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'تنظیم زمان شلوغی'
        verbose_name_plural = 'تنظیمات زمان شلوغی'
        unique_together = ['day_of_week', 'start_hour', 'end_hour']
    
    def __str__(self):
        days = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه']
        return f"{days[self.day_of_week]} {self.start_hour}:00 - {self.end_hour}:00 (x{self.multiplier})"
    