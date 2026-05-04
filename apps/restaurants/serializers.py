from rest_framework import serializers
from django.db import models
from .models import Restaurant, MenuCategory, MenuItem
from apps.accounts.serializers import UserSerializer


class RestaurantListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing restaurants
    """
    cuisine_type_display = serializers.CharField(source='get_cuisine_type_display', read_only=True)
    distance = serializers.SerializerMethodField()
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'logo', 'cuisine_type', 'cuisine_type_display',
            'minimum_order', 'delivery_time', 'is_open', 'is_busy',
            'distance', 'owner_name', 'latitude', 'longitude'
        ]
    
    def get_distance(self, obj):
        """
        Calculate distance from user - will be set in view context
        """
        distance = getattr(obj, 'distance_km', None)
        if distance:
            return round(distance, 2)
        return None


class RestaurantDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single restaurant view
    """
    cuisine_type_display = serializers.CharField(source='get_cuisine_type_display', read_only=True)
    owner = UserSerializer(read_only=True)
    categories_count = serializers.SerializerMethodField()
    menu_items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'description', 'address', 'latitude', 'longitude',
            'phone_number', 'logo', 'cover_image', 'cuisine_type', 'cuisine_type_display',
            'minimum_order', 'delivery_time', 'is_open', 'is_busy', 'is_verified',
            'max_concurrent_orders', 'current_orders_count', 'owner',
            'categories_count', 'menu_items_count', 'created_at'
        ]
    
    def get_categories_count(self, obj):
        return obj.categories.filter(is_active=True).count()
    
    def get_menu_items_count(self, obj):
        return obj.menu_items.filter(is_available=True).count()


class RestaurantCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating restaurants (owner only)
    """
    class Meta:
        model = Restaurant
        fields = [
            'name', 'description', 'address', 'latitude', 'longitude',
            'phone_number', 'logo', 'cover_image', 'cuisine_type',
            'minimum_order', 'delivery_time', 'max_concurrent_orders'
        ]
    
    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class MenuCategorySerializer(serializers.ModelSerializer):
    """
    Serializer for menu categories
    """
    items_count = serializers.SerializerMethodField()
    
    class Meta:
        model = MenuCategory
        fields = ['id', 'name', 'description', 'order', 'is_active', 'items_count']
        read_only_fields = ['id']
    
    def get_items_count(self, obj):
        return obj.items.filter(is_available=True).count()


class MenuItemListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing menu items
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'price', 'image', 'category', 'category_name',
            'is_available', 'is_featured', 'is_vegetarian', 'preparation_time',
            'status', 'status_display'
        ]


class MenuItemDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single menu item
    """
    category_name = serializers.CharField(source='category.name', read_only=True)
    restaurant_name = serializers.CharField(source='restaurant.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = MenuItem
        fields = [
            'id', 'name', 'description', 'price', 'image', 'stock',
            'is_available', 'is_featured', 'is_vegetarian', 'preparation_time',
            'status', 'status_display', 'category', 'category_name',
            'restaurant', 'restaurant_name', 'created_at'
        ]


class MenuItemCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating and updating menu items
    """
    class Meta:
        model = MenuItem
        fields = [
            'name', 'description', 'price', 'category', 'stock',
            'is_available', 'is_featured', 'is_vegetarian', 
            'preparation_time', 'status', 'image'
        ]
    
    def validate_category(self, value):
        """
        Ensure category belongs to the owner's restaurant
        """
        user = self.context['request'].user
        if value.restaurant.owner != user and not user.is_admin_user():
            raise serializers.ValidationError("این دسته به رستوران شما تعلق ندارد.")
        return value


class RestaurantStatusSerializer(serializers.ModelSerializer):
    """
    Simple serializer for toggling restaurant open/close status
    """
    class Meta:
        model = Restaurant
        fields = ['is_open', 'is_busy']
        read_only_fields = ['is_busy']


class MenuItemStockSerializer(serializers.Serializer):
    """
    Serializer for updating item stock
    """
    stock = serializers.IntegerField(min_value=0, required=True)


class NearbyRestaurantFilterSerializer(serializers.Serializer):
    """
    Query params serializer for nearby restaurants
    """
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    radius_km = serializers.IntegerField(default=5, min_value=1, max_value=50)
    cuisine = serializers.CharField(required=False, allow_blank=True)
    is_open = serializers.BooleanField(default=True, required=False)