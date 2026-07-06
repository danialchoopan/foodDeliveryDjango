from rest_framework import serializers
from .models import DeliveryTracking, RiderLocationHistory, DeliveryZone, PeakTimeSetting
from apps.orders.models import Order
from apps.accounts.models import User


class DeliveryTrackingSerializer(serializers.ModelSerializer):
    """
    Serializer for delivery tracking
    """
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    restaurant_name = serializers.CharField(source='order.restaurant.name', read_only=True)
    customer_name = serializers.SerializerMethodField()
    rider_name = serializers.CharField(source='rider.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    class Meta:
        model = DeliveryTracking
        fields = [
            'id', 'order', 'order_number', 'rider', 'rider_name', 'restaurant_name',
            'customer_name', 'status', 'status_display', 'assigned_at', 'pickup_started_at',
            'arrived_at_restaurant', 'picked_up_at', 'delivered_at', 'distance_traveled_km',
            'time_to_restaurant_minutes', 'time_to_delivery_minutes'
        ]
        read_only_fields = ['id', 'assigned_at']
    
    def get_customer_name(self, obj):
        return obj.order.customer.get_full_name() or obj.order.customer.username


class UpdateDeliveryStatusSerializer(serializers.Serializer):
    """
    Serializer for updating delivery status with location
    """
    status = serializers.ChoiceField(choices=DeliveryTracking.TrackingStatus.choices)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    
    def validate(self, attrs):
        status = attrs.get('status')
        lat = attrs.get('latitude')
        lng = attrs.get('longitude')
        
        # For location-dependent statuses, coordinates are required
        if status in [DeliveryTracking.TrackingStatus.AT_RESTAURANT, 
                      DeliveryTracking.TrackingStatus.PICKED_UP,
                      DeliveryTracking.TrackingStatus.DELIVERED]:
            if not lat or not lng:
                raise serializers.ValidationError(
                    "برای این وضعیت، موقعیت جغرافیایی الزامی است."
                )
        
        return attrs


class RiderLocationHistorySerializer(serializers.ModelSerializer):
    """
    Serializer for rider location history
    """
    rider_name = serializers.CharField(source='rider.get_full_name', read_only=True)
    
    class Meta:
        model = RiderLocationHistory
        fields = [
            'id', 'rider', 'rider_name', 'latitude', 'longitude', 
            'speed_kmh', 'bearing', 'active_order', 'recorded_at'
        ]
        read_only_fields = ['id', 'recorded_at']


class CreateRiderLocationSerializer(serializers.Serializer):
    """
    Serializer for creating a location history entry
    """
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    speed_kmh = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    bearing = serializers.IntegerField(min_value=0, max_value=359, required=False, allow_null=True)
    active_order_id = serializers.IntegerField(required=False, allow_null=True)
    
    def validate_active_order_id(self, value):
        if value:
            try:
                order = Order.objects.get(id=value)
                if order.status not in [Order.Status.READY, Order.Status.DELIVERING]:
                    raise serializers.ValidationError("این سفارش در وضعیت مناسبی برای تحویل نیست.")
                return value
            except Order.DoesNotExist:
                raise serializers.ValidationError("سفارش مورد نظر یافت نشد.")
        return value


class DeliveryZoneSerializer(serializers.ModelSerializer):
    """
    Serializer for delivery zones
    """
    class Meta:
        model = DeliveryZone
        fields = ['id', 'name', 'center_latitude', 'center_longitude', 'radius_km', 'extra_fee', 'is_active']


class PeakTimeSettingSerializer(serializers.ModelSerializer):
    """
    Serializer for peak time settings
    """
    day_display = serializers.SerializerMethodField()
    
    class Meta:
        model = PeakTimeSetting
        fields = ['id', 'day_of_week', 'day_display', 'start_hour', 'end_hour', 'multiplier', 'is_active']
    
    def get_day_display(self, obj):
        days = ['دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه', 'شنبه', 'یکشنبه']
        return days[obj.day_of_week]


class RiderPerformanceSerializer(serializers.Serializer):
    """
    Serializer for rider performance metrics
    """
    rider_id = serializers.IntegerField()
    rider_name = serializers.CharField()
    total_deliveries = serializers.IntegerField()
    completed_deliveries = serializers.IntegerField()
    cancelled_deliveries = serializers.IntegerField()
    average_delivery_time_minutes = serializers.FloatField()
    total_distance_km = serializers.FloatField()
    rating = serializers.FloatField(default=0)


class NearbyRiderSerializer(serializers.Serializer):
    """
    Serializer for finding nearby riders
    """
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=True)
    radius_km = serializers.IntegerField(default=5, min_value=1, max_value=20)
    
    def validate(self, attrs):
        lat = float(attrs['latitude'])
        lng = float(attrs['longitude'])
        # Basic validation for Iran coordinates
        if lat < 25 or lat > 40:
            raise serializers.ValidationError({"latitude": "عرض جغرافیایی نامعتبر است."})
        if lng < 44 or lng > 64:
            raise serializers.ValidationError({"longitude": "طول جغرافیایی نامعتبر است."})
        return attrs


class RiderLocationResponseSerializer(serializers.Serializer):
    """
    Response serializer for nearby riders
    """
    rider_id = serializers.IntegerField()
    rider_name = serializers.CharField()
    phone_number = serializers.CharField()
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    distance_km = serializers.FloatField()
    rider_status = serializers.CharField()
    last_location_update = serializers.DateTimeField()
    
    