from django.contrib import admin
from django.db.models import Count, Q
from django.utils.html import format_html
from .models import Restaurant, MenuCategory, MenuItem


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    """
    Admin panel for Restaurant management
    """
    list_display = ('id', 'name', 'owner', 'cuisine_type_display', 'is_open', 'is_busy', 
                   'is_verified', 'is_active', 'orders_count', 'menu_items_count', 'created_at')
    list_filter = ('cuisine_type', 'is_open', 'is_busy', 'is_verified', 'is_active', 'created_at')
    search_fields = ('name', 'owner__username', 'owner__email', 'address', 'phone_number')
    readonly_fields = ('current_orders_count', 'created_at', 'updated_at', 'show_logo')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('owner', 'name', 'description', 'cuisine_type', 'show_logo', 'logo', 'cover_image')
        }),
        ('موقعیت و تماس', {
            'fields': ('address', 'latitude', 'longitude', 'phone_number')
        }),
        ('تنظیمات سفارش', {
            'fields': ('minimum_order', 'delivery_time', 'max_concurrent_orders', 'current_orders_count')
        }),
        ('وضعیت', {
            'fields': ('is_open', 'is_busy', 'is_verified', 'is_active')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            orders_count=Count('orders', filter=Q(orders__status__in=['delivered', 'preparing', 'delivering'])),
            menu_items_count=Count('menu_items', filter=Q(menu_items__is_available=True))
        )
    
    def cuisine_type_display(self, obj):
        return obj.get_cuisine_type_display()
    cuisine_type_display.short_description = 'نوع غذا'
    cuisine_type_display.admin_order_field = 'cuisine_type'
    
    def orders_count(self, obj):
        return obj.orders_count
    orders_count.short_description = 'سفارش‌های فعال'
    orders_count.admin_order_field = 'orders_count'
    
    def menu_items_count(self, obj):
        return obj.menu_items_count
    menu_items_count.short_description = 'آیتم‌های منو'
    
    def show_logo(self, obj):
        if obj.logo:
            return format_html('<img src="{}" width="50" height="50" style="border-radius: 50%;" />', obj.logo.url)
        return '-'
    show_logo.short_description = 'لوگو'
    
    actions = ['verify_restaurants', 'unverify_restaurants', 'open_restaurants', 'close_restaurants']
    
    def verify_restaurants(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} رستوران تأیید شدند.')
    verify_restaurants.short_description = 'تأیید رستوران‌های انتخاب شده'
    
    def unverify_restaurants(self, request, queryset):
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} رستوران از حالت تأیید خارج شدند.')
    unverify_restaurants.short_description = 'لغو تأیید رستوران‌های انتخاب شده'
    
    def open_restaurants(self, request, queryset):
        updated = queryset.update(is_open=True)
        self.message_user(request, f'{updated} رستوران باز شدند.')
    open_restaurants.short_description = 'باز کردن رستوران‌های انتخاب شده'
    
    def close_restaurants(self, request, queryset):
        updated = queryset.update(is_open=False)
        self.message_user(request, f'{updated} رستوران بسته شدند.')
    close_restaurants.short_description = 'بستن رستوران‌های انتخاب شده'


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    """
    Admin panel for Menu Categories
    """
    list_display = ('id', 'name', 'restaurant', 'order', 'is_active', 'items_count')
    list_filter = ('is_active', 'restaurant')
    search_fields = ('name', 'restaurant__name')
    ordering = ('restaurant', 'order', 'name')
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(items_count=Count('items'))
    
    def items_count(self, obj):
        return obj.items_count
    items_count.short_description = 'تعداد آیتم‌ها'


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    """
    Admin panel for Menu Items
    """
    list_display = ('id', 'name', 'restaurant', 'category', 'price', 'stock', 
                   'is_available', 'is_featured', 'preparation_time', 'show_image')
    list_filter = ('is_available', 'is_featured', 'is_vegetarian', 'status', 'restaurant', 'category')
    search_fields = ('name', 'description', 'restaurant__name')
    readonly_fields = ('created_at', 'updated_at', 'show_image')
    ordering = ('restaurant', 'category', 'name')
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('restaurant', 'category', 'name', 'description', 'show_image', 'image')
        }),
        ('قیمت و موجودی', {
            'fields': ('price', 'stock', 'is_available', 'status')
        }),
        ('ویژگی‌ها', {
            'fields': ('is_featured', 'is_vegetarian', 'preparation_time')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def show_image(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="50" height="50" style="object-fit: cover;" />', obj.image.url)
        return '-'
    show_image.short_description = 'تصویر'
    
    actions = ['make_available', 'make_unavailable', 'make_featured', 'make_not_featured']
    
    def make_available(self, request, queryset):
        updated = queryset.update(is_available=True, status=MenuItem.ItemStatus.AVAILABLE)
        self.message_user(request, f'{updated} آیتم موجود شدند.')
    make_available.short_description = 'موجود کردن آیتم‌های انتخاب شده'
    
    def make_unavailable(self, request, queryset):
        updated = queryset.update(is_available=False, status=MenuItem.ItemStatus.UNAVAILABLE)
        self.message_user(request, f'{updated} آیتم ناموجود شدند.')
    make_unavailable.short_description = 'ناموجود کردن آیتم‌های انتخاب شده'
    
    def make_featured(self, request, queryset):
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} آیتم ویژه شدند.')
    make_featured.short_description = 'ویژه کردن آیتم‌های انتخاب شده'
    
    def make_not_featured(self, request, queryset):
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} آیتم از حالت ویژه خارج شدند.')
    make_not_featured.short_description = 'خارج کردن از حالت ویژه'
    