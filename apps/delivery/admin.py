from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Count, Sum, Avg
from .models import DeliveryTracking, RiderLocationHistory, DeliveryZone, PeakTimeSetting
from apps.accounts.models import User


@admin.register(DeliveryTracking)
class DeliveryTrackingAdmin(admin.ModelAdmin):
    """
    Admin panel for Delivery Tracking
    """
    list_display = ('id', 'order', 'rider', 'status_colored', 'assigned_at', 
                   'picked_up_at', 'delivered_at', 'delivery_time')
    list_filter = ('status', 'assigned_at', 'delivered_at')
    search_fields = ('order__order_number', 'rider__username', 'rider__phone_number')
    readonly_fields = ('assigned_at', 'created_at', 'updated_at', 'show_timeline', 
                      'distance_traveled_km', 'time_to_restaurant_minutes', 'time_to_delivery_minutes')
    ordering = ('-assigned_at',)
    
    fieldsets = (
        ('اطلاعات اصلی', {
            'fields': ('order', 'rider', 'status', 'show_timeline')
        }),
        ('زمان‌های کلیدی', {
            'fields': ('assigned_at', 'pickup_started_at', 'arrived_at_restaurant', 
                      'picked_up_at', 'delivered_at')
        }),
        ('موقعیت‌های ثبت شده', {
            'fields': ('restaurant_arrival_latitude', 'restaurant_arrival_longitude',
                      'pickup_latitude', 'pickup_longitude',
                      'delivery_latitude', 'delivery_longitude'),
            'classes': ('collapse',)
        }),
        ('شاخص‌های عملکرد', {
            'fields': ('distance_traveled_km', 'time_to_restaurant_minutes', 'time_to_delivery_minutes'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('order', 'rider')
    
    def status_colored(self, obj):
        colors = {
            'pending': 'gray',
            'pickup': 'orange',
            'at_restaurant': 'blue',
            'picked_up': 'purple',
            'delivering': 'cyan',
            'delivered': 'green',
            'failed': 'red',
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', 
                          color, obj.get_status_display())
    status_colored.short_description = 'وضعیت'
    status_colored.admin_order_field = 'status'
    
    def delivery_time(self, obj):
        if obj.delivered_at and obj.picked_up_at:
            minutes = (obj.delivered_at - obj.picked_up_at).total_seconds() / 60
            return f"{int(minutes)} دقیقه"
        return '-'
    delivery_time.short_description = 'زمان تحویل'
    
    def show_timeline(self, obj):
        timeline_html = '<div style="direction: rtl;">'
        
        milestones = [
            ('assigned_at', '📋 اختصاص به راننده'),
            ('arrived_at_restaurant', '🏠 رسیدن به رستوران'),
            ('picked_up_at', '🍔 تحویل گرفتن سفارش'),
            ('delivered_at', '✅ تحویل به مشتری'),
        ]
        
        for field, label in milestones:
            time_value = getattr(obj, field)
            if time_value:
                timeline_html += f'<div style="margin: 5px 0;">{label}: {time_value.strftime("%Y-%m-%d %H:%M")}</div>'
            else:
                timeline_html += f'<div style="margin: 5px 0; color: gray;">{label}: در انتظار...</div>'
        
        timeline_html += '</div>'
        return format_html(timeline_html)
    show_timeline.short_description = 'روند زمانی'
    
    actions = ['mark_as_pickup', 'mark_as_arrived', 'mark_as_picked_up', 'mark_as_delivered']
    
    def mark_as_pickup(self, request, queryset):
        for tracking in queryset.filter(status='pending'):
            tracking.update_status(DeliveryTracking.TrackingStatus.PICKUP)
        self.message_user(request, f'{queryset.count()} سفارش در مسیر رستوران شد.')
    mark_as_pickup.short_description = 'در مسیر رستوران'
    
    def mark_as_arrived(self, request, queryset):
        for tracking in queryset.filter(status='pickup'):
            tracking.update_status(DeliveryTracking.TrackingStatus.AT_RESTAURANT)
        self.message_user(request, f'{queryset.count()} سفارش به رستوران رسید.')
    mark_as_arrived.short_description = 'رسیدن به رستوران'
    
    def mark_as_picked_up(self, request, queryset):
        for tracking in queryset.filter(status='at_restaurant'):
            tracking.update_status(DeliveryTracking.TrackingStatus.PICKED_UP)
        self.message_user(request, f'{queryset.count()} سفارش تحویل گرفته شد.')
    mark_as_picked_up.short_description = 'تحویل گرفتن سفارش'
    
    def mark_as_delivered(self, request, queryset):
        for tracking in queryset.filter(status='picked_up'):
            tracking.update_status(DeliveryTracking.TrackingStatus.DELIVERED)
            # Update order status
            order = tracking.order
            order.update_status(Order.Status.DELIVERED)
            # Free the rider
            if tracking.rider:
                tracking.rider.rider_status = User.RiderStatus.AVAILABLE
                tracking.rider.save(update_fields=['rider_status'])
        self.message_user(request, f'{queryset.count()} سفارش تحویل داده شد.')
    mark_as_delivered.short_description = 'تحویل به مشتری'


@admin.register(RiderLocationHistory)
class RiderLocationHistoryAdmin(admin.ModelAdmin):
    """
    Admin panel for Rider Location History
    """
    list_display = ('id', 'rider', 'latitude', 'longitude', 'speed_kmh', 'bearing', 'recorded_at')
    list_filter = ('recorded_at',)
    search_fields = ('rider__username', 'rider__phone_number')
    readonly_fields = ('recorded_at',)
    ordering = ('-recorded_at',)
    
    fieldsets = (
        ('اطلاعات راننده', {
            'fields': ('rider', 'active_order')
        }),
        ('موقعیت', {
            'fields': ('latitude', 'longitude', 'speed_kmh', 'bearing')
        }),
        ('زمان', {
            'fields': ('recorded_at',)
        }),
    )


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    """
    Admin panel for Delivery Zones
    """
    list_display = ('name', 'center_latitude', 'center_longitude', 'radius_km', 'extra_fee', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('name',)
    
    fieldsets = (
        ('اطلاعات منطقه', {
            'fields': ('name', 'is_active')
        }),
        ('موقعیت جغرافیایی', {
            'fields': ('center_latitude', 'center_longitude', 'radius_km')
        }),
        ('هزینه اضافی', {
            'fields': ('extra_fee',)
        }),
    )
    
    actions = ['activate_zones', 'deactivate_zones']
    
    def activate_zones(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} منطقه فعال شد.')
    activate_zones.short_description = 'فعال کردن مناطق انتخاب شده'
    
    def deactivate_zones(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} منطقه غیرفعال شد.')
    deactivate_zones.short_description = 'غیرفعال کردن مناطق انتخاب شده'


@admin.register(PeakTimeSetting)
class PeakTimeSettingAdmin(admin.ModelAdmin):
    """
    Admin panel for Peak Time Settings
    """
    list_display = ('day_of_week_display', 'start_hour', 'end_hour', 'multiplier', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    ordering = ('day_of_week', 'start_hour')
    
    def day_of_week_display(self, obj):
        days = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه']
        return days[obj.day_of_week]
    day_of_week_display.short_description = 'روز هفته'
    day_of_week_display.admin_order_field = 'day_of_week'
    
    fieldsets = (
        ('تنظیمات زمان شلوغی', {
            'fields': ('day_of_week', 'start_hour', 'end_hour', 'multiplier', 'is_active')
        }),
    )
    
    actions = ['activate_settings', 'deactivate_settings']
    
    def activate_settings(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} تنظیمات فعال شد.')
    activate_settings.short_description = 'فعال کردن تنظیمات انتخاب شده'
    
    def deactivate_settings(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} تنظیمات غیرفعال شد.')
    deactivate_settings.short_description = 'غیرفعال کردن تنظیمات انتخاب شده'
    