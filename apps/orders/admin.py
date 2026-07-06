from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.db.models import Sum, Count, Q
from .models import Order, OrderItem, Cart, CartItem


class OrderItemInline(admin.TabularInline):
    """
    Inline admin for Order items
    """
    model = OrderItem
    extra = 0
    readonly_fields = ('menu_item', 'quantity', 'price', 'total', 'item_name')
    fields = ('menu_item', 'item_name', 'quantity', 'price', 'total')
    can_delete = False
    show_change_link = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin panel for Order management
    """
    list_display = ('order_number', 'customer', 'restaurant', 'rider', 'total_amount', 
                   'status_colored', 'payment_method', 'is_paid', 'created_at', 'action_buttons')
    list_filter = ('status', 'payment_method', 'is_paid', 'created_at', 'restaurant')
    search_fields = ('order_number', 'customer__username', 'customer__email', 
                    'restaurant__name', 'customer__phone_number')
    readonly_fields = ('order_number', 'created_at', 'updated_at', 'confirmed_at', 
                      'ready_at', 'delivered_at', 'cancelled_at', 'show_timeline')
    ordering = ('-created_at',)
    
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('اطلاعات سفارش', {
            'fields': ('order_number', 'customer', 'restaurant', 'rider', 'show_timeline')
        }),
        ('مبالغ', {
            'fields': ('subtotal', 'delivery_fee', 'discount', 'total_amount')
        }),
        ('آدرس و موقعیت', {
            'fields': ('delivery_address', 'customer_latitude', 'customer_longitude', 'distance_km')
        }),
        ('وضعیت', {
            'fields': ('status', 'payment_method', 'is_paid', 'customer_note', 'rider_note')
        }),
        ('زمان‌ها', {
            'fields': ('created_at', 'confirmed_at', 'ready_at', 'delivered_at', 'cancelled_at', 'updated_at'),
            'classes': ('collapse',)
        }),
        ('زمان تخمینی', {
            'fields': ('estimated_delivery_time', 'preparation_time'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'restaurant', 'rider')
    
    def status_colored(self, obj):
        colors = {
            'pending': 'orange',
            'confirmed': 'blue',
            'preparing': 'purple',
            'ready': 'green',
            'delivering': 'cyan',
            'delivered': 'darkgreen',
            'cancelled': 'red',
            'rejected': 'darkred',
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', 
                          color, obj.get_status_display())
    status_colored.short_description = 'وضعیت'
    status_colored.admin_order_field = 'status'
    
    def show_timeline(self, obj):
        timeline_html = '<div style="direction: rtl;">'
        statuses = [
            ('created_at', 'ثبت سفارش', 'created'),
            ('confirmed_at', 'تأیید شده', 'confirmed'),
            ('ready_at', 'آماده تحویل', 'ready'),
            ('delivered_at', 'تحویل داده شده', 'delivered'),
        ]
        
        for field, label, icon in statuses:
            time_value = getattr(obj, field)
            if time_value:
                timeline_html += f'<div>✅ {label}: {time_value.strftime("%Y-%m-%d %H:%M")}</div>'
            else:
                timeline_html += f'<div>⏳ {label}: در انتظار...</div>'
        
        timeline_html += '</div>'
        return format_html(timeline_html)
    show_timeline.short_description = 'روند زمانی'
    
    def action_buttons(self, obj):
        buttons = []
        if obj.status == 'pending':
            buttons.append(f'<a class="button" href="/admin/orders/order/{obj.id}/confirm/" style="background:green; color:white; padding:3px 8px; text-decoration:none; margin:2px;">✅ تأیید</a>')
            buttons.append(f'<a class="button" href="/admin/orders/order/{obj.id}/cancel/" style="background:red; color:white; padding:3px 8px; text-decoration:none; margin:2px;">❌ لغو</a>')
        elif obj.status == 'confirmed':
            buttons.append(f'<a class="button" href="/admin/orders/order/{obj.id}/prepare/" style="background:blue; color:white; padding:3px 8px; text-decoration:none; margin:2px;">👨‍🍳 شروع آماده‌سازی</a>')
        elif obj.status == 'preparing':
            buttons.append(f'<a class="button" href="/admin/orders/order/{obj.id}/ready/" style="background:purple; color:white; padding:3px 8px; text-decoration:none; margin:2px;">✅ آماده تحویل</a>')
        
        return format_html(' '.join(buttons)) if buttons else '-'
    action_buttons.short_description = 'عملیات سریع'
    
    actions = ['mark_as_confirmed', 'mark_as_preparing', 'mark_as_ready', 'mark_as_delivered', 'cancel_orders']
    
    def mark_as_confirmed(self, request, queryset):
        for order in queryset.filter(status='pending'):
            order.update_status(Order.Status.CONFIRMED)
        self.message_user(request, f'{queryset.count()} سفارش تأیید شد.')
    mark_as_confirmed.short_description = 'تأیید سفارش‌های انتخاب شده'
    
    def mark_as_preparing(self, request, queryset):
        for order in queryset.filter(status='confirmed'):
            order.update_status(Order.Status.PREPARING)
        self.message_user(request, f'{queryset.count()} سفارش در حال آماده‌سازی شد.')
    mark_as_preparing.short_description = 'آماده‌سازی سفارش‌های انتخاب شده'
    
    def mark_as_ready(self, request, queryset):
        for order in queryset.filter(status='preparing'):
            order.update_status(Order.Status.READY)
        self.message_user(request, f'{queryset.count()} سفارش آماده تحویل شد.')
    mark_as_ready.short_description = 'آماده تحویل کردن سفارش‌ها'
    
    def mark_as_delivered(self, request, queryset):
        for order in queryset.filter(status='delivering'):
            order.update_status(Order.Status.DELIVERED)
        self.message_user(request, f'{queryset.count()} سفارش تحویل داده شد.')
    mark_as_delivered.short_description = 'تحویل سفارش‌های انتخاب شده'
    
    def cancel_orders(self, request, queryset):
        from .services import OrderCancellationService
        success_count = 0
        for order in queryset.filter(status__in=['pending', 'confirmed']):
            success, _ = OrderCancellationService.cancel_order_with_lock(order.id, request.user)
            if success:
                success_count += 1
        self.message_user(request, f'{success_count} سفارش لغو شد.')
    cancel_orders.short_description = 'لغو سفارش‌های انتخاب شده'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    """
    Admin panel for Order Items
    """
    list_display = ('id', 'order', 'item_name', 'quantity', 'price', 'total', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('order__order_number', 'item_name', 'menu_item__name')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)


class CartItemInline(admin.TabularInline):
    """
    Inline admin for Cart items
    """
    model = CartItem
    extra = 0
    readonly_fields = ('menu_item', 'quantity')
    fields = ('menu_item', 'quantity')
    can_delete = True


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Admin panel for Shopping Carts
    """
    list_display = ('id', 'customer', 'items_count', 'total_price', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('customer__username', 'customer__email')
    readonly_fields = ('created_at', 'updated_at', 'items_count', 'total_price')
    
    inlines = [CartItemInline]
    
    def items_count(self, obj):
        return obj.items.count()
    items_count.short_description = 'تعداد آیتم‌ها'
    
    def total_price(self, obj):
        total = sum(item.menu_item.price * item.quantity for item in obj.items.all())
        return format_html('<b>{:,.0f} تومان</b>', total)
    total_price.short_description = 'جمع کل'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Admin panel for Cart Items
    """
    list_display = ('id', 'cart', 'menu_item', 'quantity', 'total')
    list_filter = ('created_at',)
    search_fields = ('cart__customer__username', 'menu_item__name')
    readonly_fields = ('created_at', 'updated_at')
    
    def total(self, obj):
        return f"{obj.menu_item.price * obj.quantity:,} تومان"
    total.short_description = 'جمع'
    