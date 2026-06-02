from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserOTP, Address


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'city', 'is_default', 'is_active', 'created_at')
    list_filter = ('city', 'is_default', 'is_active')
    search_fields = ('user__username', 'title', 'address_text')


class CustomUserAdmin(UserAdmin):
    """
    Custom admin panel for User model with role-based fields
    """
    list_display = ('username', 'email', 'phone_number', 'get_full_name', 'role', 'is_active', 'is_verified', 'date_joined')
    list_filter = ('role', 'is_active', 'is_verified', 'is_staff', 'is_superuser', 'rider_status')
    search_fields = ('username', 'email', 'phone_number', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'avatar')}),
        (_('Role & Permissions'), {
            'fields': ('role', 'is_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Rider Specific'), {
            'fields': ('rider_status', 'current_latitude', 'current_longitude', 'last_location_update'),
            'classes': ('collapse',),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone_number', 'password1', 'password2', 'role'),
        }),
    )
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    get_full_name.short_description = 'نام کامل'
    
    actions = ['verify_users', 'make_customer', 'make_restaurant_owner', 'make_delivery_rider']
    
    def verify_users(self, request, queryset):
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} کاربر تأیید شدند.')
    verify_users.short_description = 'تأیید کاربران انتخاب شده'
    
    def make_customer(self, request, queryset):
        updated = queryset.update(role=User.Role.CUSTOMER)
        self.message_user(request, f'{updated} کاربر به نقش مشتری تغییر یافتند.')
    make_customer.short_description = 'تبدیل به مشتری'
    
    def make_restaurant_owner(self, request, queryset):
        updated = queryset.update(role=User.Role.RESTAURANT_OWNER)
        self.message_user(request, f'{updated} کاربر به نقش صاحب رستوران تغییر یافتند.')
    make_restaurant_owner.short_description = 'تبدیل به صاحب رستوران'
    
    def make_delivery_rider(self, request, queryset):
        updated = queryset.update(role=User.Role.DELIVERY_RIDER)
        self.message_user(request, f'{updated} کاربر به نقش راننده تغییر یافتند.')
    make_delivery_rider.short_description = 'تبدیل به راننده'


class UserOTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'created_at', 'is_used', 'is_valid')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__username', 'user__phone_number', 'code')
    readonly_fields = ('created_at',)
    
    def is_valid(self, obj):
        return obj.is_valid()
    is_valid.boolean = True
    is_valid.short_description = 'معتبر'


admin.site.register(User, CustomUserAdmin)
admin.site.register(UserOTP, UserOTPAdmin)
