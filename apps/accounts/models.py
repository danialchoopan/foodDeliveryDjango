from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class User(AbstractUser):
    """
    Custom User model with role-based access control
    """
    class Role(models.TextChoices):
        CUSTOMER = 'customer', 'مشتری'
        RESTAURANT_OWNER = 'restaurant_owner', 'صاحب رستوران'
        DELIVERY_RIDER = 'delivery_rider', 'راننده تحویل'
        ADMIN = 'admin', 'مدیر سیستم'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        verbose_name='نقش کاربری'
    )
    
    # Additional fields for delivery rider
    phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # Geolocation for delivery riders (real-time position)
    current_latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True,
        verbose_name='طول جغرافیایی فعلی'
    )
    current_longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        null=True, 
        blank=True,
        verbose_name='عرض جغرافیایی فعلی'
    )
    last_location_update = models.DateTimeField(null=True, blank=True)
    
    # Rider status
    class RiderStatus(models.TextChoices):
        AVAILABLE = 'available', 'آماده به کار'
        BUSY = 'busy', 'در حال تحویل'
        OFFLINE = 'offline', 'آفلاین'
    
    rider_status = models.CharField(
        max_length=10,
        choices=RiderStatus.choices,
        default=RiderStatus.OFFLINE,
        verbose_name='وضعیت راننده'
    )
    
    # For restaurant owners
    is_verified = models.BooleanField(default=False, verbose_name='تأیید شده')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['role']),
            models.Index(fields=['phone_number']),
        ]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    def is_customer(self):
        return self.role == self.Role.CUSTOMER

    def is_restaurant_owner(self):
        return self.role == self.Role.RESTAURANT_OWNER

    def is_delivery_rider(self):
        return self.role == self.Role.DELIVERY_RIDER

    def is_admin_user(self):
        return self.is_staff or self.is_superuser or self.role == self.Role.ADMIN

    def update_location(self, latitude, longitude):
        """
        Update rider's current location
        """
        if self.is_delivery_rider():
            self.current_latitude = latitude
            self.current_longitude = longitude
            self.last_location_update = timezone.now()
            self.save(update_fields=['current_latitude', 'current_longitude', 'last_location_update'])

    def get_location(self):
        """
        Get rider's current location as tuple
        """
        if self.current_latitude and self.current_longitude:
            return (float(self.current_latitude), float(self.current_longitude))
        return None

    def is_available_for_delivery(self):
        """
        Check if rider is available to accept new orders
        """
        return (self.is_delivery_rider() and 
                self.rider_status == self.RiderStatus.AVAILABLE and
                self.is_active)

    def save(self, *args, **kwargs):
        # If user is superuser or staff, set role to admin
        if self.is_superuser or self.is_staff:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)


class UserOTP(models.Model):
    """
    OTP model for phone number verification (optional)
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'کد تایید'
        verbose_name_plural = 'کدهای تایید'

    def is_valid(self):
        from datetime import timedelta
        return not self.is_used and timezone.now() - self.created_at < timedelta(minutes=5)