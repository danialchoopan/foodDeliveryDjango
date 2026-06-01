from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.db.models import Avg
from apps.accounts.models import User


class Restaurant(models.Model):
    """
    Restaurant model for food delivery system
    """
    class CuisineType(models.TextChoices):
        PERSIAN = 'persian', 'ایرانی'
        FAST_FOOD = 'fast_food', 'فست فود'
        ITALIAN = 'italian', 'ایتالیایی'
        CHINESE = 'chinese', 'چینی'
        JAPANESE = 'japanese', 'ژاپنی'
        DESSERT = 'dessert', 'دسر و شیرینی'
        CAFE = 'cafe', 'کافه'
        OTHER = 'other', 'سایر'

    owner = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='restaurants',
        limit_choices_to={'role': User.Role.RESTAURANT_OWNER}
    )
    name = models.CharField(max_length=255, verbose_name='نام رستوران')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    
    # Location fields
    address = models.TextField(verbose_name='آدرس')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='طول جغرافیایی')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='عرض جغرافیایی')
    
    # Contact info
    phone_number = models.CharField(max_length=15, verbose_name='شماره تلفن')
    logo = models.ImageField(upload_to='restaurant_logos/', null=True, blank=True)
    cover_image = models.ImageField(upload_to='restaurant_covers/', null=True, blank=True)
    
    # Restaurant details
    cuisine_type = models.CharField(
        max_length=20, 
        choices=CuisineType.choices, 
        default=CuisineType.PERSIAN,
        verbose_name='نوع غذا'
    )
    minimum_order = models.DecimalField(
        max_digits=10, 
        decimal_places=0, 
        default=0,
        verbose_name='حداقل سفارش'
    )
    delivery_time = models.PositiveIntegerField(
        default=30,
        help_text='زمان تخمینی تحویل به دقیقه',
        verbose_name='زمان تحویل'
    )
    
    # Status fields
    is_open = models.BooleanField(default=True, verbose_name='باز است')
    is_verified = models.BooleanField(default=False, verbose_name='تأیید شده')
    is_busy = models.BooleanField(default=False, verbose_name='مشغول است')  # Auto-set when order queue is full
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    
    # Order management
    max_concurrent_orders = models.PositiveIntegerField(
        default=20,
        help_text='حداکثر سفارش‌های همزمان',
        verbose_name='حداکثر سفارش همزمان'
    )
    current_orders_count = models.PositiveIntegerField(default=0, verbose_name='تعداد سفارش‌های جاری')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'رستوران'
        verbose_name_plural = 'رستوران‌ها'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['is_open', 'is_active']),
            models.Index(fields=['cuisine_type']),
            models.Index(fields=['owner']),
        ]

    def __str__(self):
        return f"{self.name} - {self.get_cuisine_type_display()}"

    def increment_order_count(self):
        """
        Increase current order count and check if restaurant becomes busy
        """
        from django.db import transaction
        with transaction.atomic():
            self.current_orders_count += 1
            if self.current_orders_count >= self.max_concurrent_orders:
                self.is_busy = True
            self.save(update_fields=['current_orders_count', 'is_busy'])

    def decrement_order_count(self):
        """
        Decrease current order count and update busy status
        """
        from django.db import transaction
        with transaction.atomic():
            self.current_orders_count = max(0, self.current_orders_count - 1)
            if self.current_orders_count < self.max_concurrent_orders:
                self.is_busy = False
            self.save(update_fields=['current_orders_count', 'is_busy'])

    def can_accept_new_order(self):
        """
        Check if restaurant can accept a new order
        """
        return self.is_open and self.is_active and self.is_verified and not self.is_busy

    def get_location(self):
        """
        Return restaurant location as tuple
        """
        return (float(self.latitude), float(self.longitude))

    def save(self, *args, **kwargs):
        if not self.pk:  # New restaurant
            self.is_verified = False  # Requires admin approval
        super().save(*args, **kwargs)

    @property
    def average_rating(self):
        return self.reviews.aggregate(Avg('rating'))['rating__avg'] or 0


class RestaurantReview(models.Model):
    """
    Review and rating for a restaurant
    """
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restaurant_reviews')
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name='امتیاز'
    )
    comment = models.TextField(blank=True, verbose_name='نظر')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'نظر رستوران'
        verbose_name_plural = 'نظرات رستوران'
        unique_together = ['restaurant', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.restaurant.name} ({self.rating})"


class FavoriteRestaurant(models.Model):
    """
    User's favorite restaurants
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'رستوران مورد علاقه'
        verbose_name_plural = 'رستوران‌های مورد علاقه'
        unique_together = ['user', 'restaurant']

    def __str__(self):
        return f"{self.user.username} liked {self.restaurant.name}"


class MenuCategory(models.Model):
    """
    Category for menu items (e.g., Appetizers, Main Dishes, Drinks)
    """
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100, verbose_name='نام دسته')
    description = models.CharField(max_length=255, blank=True, verbose_name='توضیحات')
    order = models.PositiveIntegerField(default=0, verbose_name='ترتیب نمایش')
    is_active = models.BooleanField(default=True, verbose_name='فعال')

    class Meta:
        verbose_name = 'دسته منو'
        verbose_name_plural = 'دسته‌های منو'
        ordering = ['order', 'name']
        unique_together = ['restaurant', 'name']

    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"


class MenuItem(models.Model):
    """
    Individual food/drink item in restaurant menu
    """
    class ItemStatus(models.TextChoices):
        AVAILABLE = 'available', 'موجود'
        UNAVAILABLE = 'unavailable', 'ناموجود'
        COMING_SOON = 'coming_soon', 'به زودی'

    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    category = models.ForeignKey(MenuCategory, on_delete=models.CASCADE, related_name='items', null=True, blank=True)
    
    name = models.CharField(max_length=255, verbose_name='نام غذا')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    price = models.DecimalField(max_digits=10, decimal_places=0, validators=[MinValueValidator(0)], verbose_name='قیمت')
    
    # Stock management
    stock = models.PositiveIntegerField(default=0, verbose_name='موجودی')
    is_available = models.BooleanField(default=True, verbose_name='موجود است')
    
    # Media
    image = models.ImageField(upload_to='menu_items/', null=True, blank=True)
    
    # Flags
    is_featured = models.BooleanField(default=False, verbose_name='ویژه')
    is_vegetarian = models.BooleanField(default=False, verbose_name='گیاه‌خواری')
    preparation_time = models.PositiveIntegerField(
        default=15,
        help_text='زمان آماده‌سازی به دقیقه',
        verbose_name='زمان آماده‌سازی'
    )
    
    status = models.CharField(
        max_length=15,
        choices=ItemStatus.choices,
        default=ItemStatus.AVAILABLE,
        verbose_name='وضعیت'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'آیتم منو'
        verbose_name_plural = 'آیتم‌های منو'
        ordering = ['category__order', 'name']
        indexes = [
            models.Index(fields=['restaurant', 'is_available']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.name} - {self.price:,} تومان"

    def deduct_stock(self, quantity=1):
        """
        Deduct stock when order is placed with select_for_update lock
        """
        if self.stock >= quantity:
            self.stock -= quantity
            if self.stock == 0:
                self.is_available = False
                self.status = self.ItemStatus.UNAVAILABLE
            self.save(update_fields=['stock', 'is_available', 'status'])
            return True
        return False
    