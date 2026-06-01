from rest_framework import generics, viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import DeliveryTracking, RiderLocationHistory, DeliveryZone, PeakTimeSetting
from .serializers import (
    DeliveryTrackingSerializer, UpdateDeliveryStatusSerializer,
    RiderLocationHistorySerializer, CreateRiderLocationSerializer,
    DeliveryZoneSerializer, PeakTimeSettingSerializer, NearbyRiderSerializer,
    RiderLocationResponseSerializer, RiderPerformanceSerializer
)
from .services import (
    RiderMatchingService, DeliveryFeeCalculator, 
    RiderPerformanceService, DeliveryTrackingService
)
from apps.accounts.permissions import IsDeliveryRider, IsAdminUser, IsDeliveryRiderOrAdmin
from apps.orders.models import Order
from apps.accounts.models import User


@extend_schema_view(
    list=extend_schema(summary="لیست ردیابی‌های تحویل"),
    retrieve=extend_schema(summary="جزییات ردیابی تحویل"),
)
class DeliveryTrackingViewSet(viewsets.GenericViewSet):
    """
    ViewSet for delivery tracking management
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user():
            return DeliveryTracking.objects.all()
        elif user.is_delivery_rider():
            return DeliveryTracking.objects.filter(rider=user)
        else:
            # Customer can see tracking for their orders
            return DeliveryTracking.objects.filter(order__customer=user)
    
    def get_serializer_class(self):
        return DeliveryTrackingSerializer
    
    def list(self, request):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def retrieve(self, request, pk=None):
        tracking = get_object_or_404(self.get_queryset(), id=pk)
        serializer = self.get_serializer(tracking)
        return Response(serializer.data)
    
    @extend_schema(
        request=UpdateDeliveryStatusSerializer,
        summary="بروزرسانی وضعیت تحویل (فقط راننده)"
    )
    @action(detail=True, methods=['patch'], url_path='status', permission_classes=[IsDeliveryRider])
    def update_status(self, request, pk=None):
        tracking = get_object_or_404(DeliveryTracking, id=pk, rider=request.user)
        serializer = UpdateDeliveryStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        status_val = serializer.validated_data['status']
        latitude = serializer.validated_data.get('latitude')
        longitude = serializer.validated_data.get('longitude')
        
        tracking.update_status(status_val, latitude, longitude)
        
        # If delivery completed, update order status and free the rider
        if status_val == DeliveryTracking.TrackingStatus.DELIVERED:
            order = tracking.order
            order.update_status(Order.Status.DELIVERED)
            # Free the rider
            rider = request.user
            rider.rider_status = User.RiderStatus.AVAILABLE
            rider.save(update_fields=['rider_status'])
        
        return Response(DeliveryTrackingSerializer(tracking).data)
    
    @extend_schema(summary="دریافت موقعیت لحظه‌ای سفارش (برای مشتری)")
    @action(detail=True, methods=['get'], url_path='live-location')
    def live_location(self, request, pk=None):
        """Get live location of rider for this order"""
        tracking = get_object_or_404(self.get_queryset(), id=pk)
        
        if not tracking.rider:
            return Response({"error": "راننده‌ای به این سفارش اختصاص داده نشده است."},
                          status=status.HTTP_404_NOT_FOUND)
        
        # Get rider's current location
        rider = tracking.rider
        if rider.current_latitude and rider.current_longitude:
            return Response({
                'order_id': tracking.order.id,
                'order_number': tracking.order.order_number,
                'rider_id': rider.id,
                'rider_name': rider.get_full_name() or rider.username,
                'latitude': float(rider.current_latitude),
                'longitude': float(rider.current_longitude),
                'last_update': rider.last_location_update,
                'status': tracking.status
            })
        
        return Response({"error": "موقعیت راننده در دسترس نیست."},
                      status=status.HTTP_404_NOT_FOUND)


@extend_schema_view(
    list=extend_schema(summary="تاریخچه موقعیت راننده"),
)
class RiderLocationHistoryViewSet(viewsets.GenericViewSet):
    """
    ViewSet for rider location history
    """
    permission_classes = [IsAuthenticated, IsDeliveryRiderOrAdmin]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_admin_user():
            rider_id = self.request.query_params.get('rider_id')
            if rider_id:
                return RiderLocationHistory.objects.filter(rider_id=rider_id)
            return RiderLocationHistory.objects.all()
        return RiderLocationHistory.objects.filter(rider=user)
    
    def get_serializer_class(self):
        return RiderLocationHistorySerializer
    
    def list(self, request):
        # Get last N records (default 50)
        limit = int(request.query_params.get('limit', 50))
        queryset = self.get_queryset()[:limit]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @extend_schema(
        request=CreateRiderLocationSerializer,
        summary="ثبت موقعیت لحظه‌ای راننده"
    )
    @action(detail=False, methods=['post'], url_path='record', permission_classes=[IsDeliveryRider])
    def record_location(self, request):
        """Record current rider location"""
        serializer = CreateRiderLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        rider = request.user
        latitude = serializer.validated_data['latitude']
        longitude = serializer.validated_data['longitude']
        
        # Update rider's current location
        rider.update_location(latitude, longitude)
        
        # Create history record
        history = RiderLocationHistory.objects.create(
            rider=rider,
            latitude=latitude,
            longitude=longitude,
            speed_kmh=serializer.validated_data.get('speed_kmh'),
            bearing=serializer.validated_data.get('bearing'),
            active_order_id=serializer.validated_data.get('active_order_id')
        )
        
        return Response(RiderLocationHistorySerializer(history).data, status=status.HTTP_201_CREATED)


class NearbyRidersView(generics.GenericAPIView):
    """
    Find nearby available riders
    """
    permission_classes = [IsAuthenticated]
    serializer_class = NearbyRiderSerializer
    
    @extend_schema(
        request=NearbyRiderSerializer,
        responses={200: RiderLocationResponseSerializer(many=True)},
        summary="یافتن راننده‌های نزدیک"
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        latitude = float(serializer.validated_data['latitude'])
        longitude = float(serializer.validated_data['longitude'])
        radius_km = serializer.validated_data['radius_km']
        
        riders = RiderMatchingService.find_nearest_available_riders(
            latitude, longitude, radius_km
        )
        
        return Response(riders)


class DeliveryFeeView(generics.GenericAPIView):
    """
    Calculate delivery fee based on distance and peak time
    """
    permission_classes = [IsAuthenticated]
    
    @extend_schema(
        summary="محاسبه هزینه ارسال",
        request={
            'type': 'object',
            'properties': {
                'restaurant_latitude': {'type': 'number'},
                'restaurant_longitude': {'type': 'number'},
                'customer_latitude': {'type': 'number'},
                'customer_longitude': {'type': 'number'},
                'base_fee': {'type': 'integer', 'default': 5000},
                'fee_per_km': {'type': 'integer', 'default': 2000}
            },
            'required': ['restaurant_latitude', 'restaurant_longitude', 'customer_latitude', 'customer_longitude']
        }
    )
    def post(self, request):
        data = request.data
        
        required_fields = ['restaurant_latitude', 'restaurant_longitude', 
                          'customer_latitude', 'customer_longitude']
        
        for field in required_fields:
            if field not in data:
                return Response({"error": f"{field} الزامی است."},
                              status=status.HTTP_400_BAD_REQUEST)
        
        result = DeliveryFeeCalculator.calculate_fee(
            restaurant_lat=float(data['restaurant_latitude']),
            restaurant_lng=float(data['restaurant_longitude']),
            customer_lat=float(data['customer_latitude']),
            customer_lng=float(data['customer_longitude']),
            base_fee=int(data.get('base_fee', 5000)),
            fee_per_km=int(data.get('fee_per_km', 2000))
        )
        
        return Response(result)


class RiderPerformanceView(generics.GenericAPIView):
    """
    Get rider performance metrics
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @extend_schema(
        responses={200: RiderPerformanceSerializer},
        summary="گزارش عملکرد راننده"
    )
    def get(self, request, rider_id=None):
        if rider_id:
            # Get performance for specific rider
            performance = RiderPerformanceService.get_rider_performance(rider_id)
            return Response(performance)
        else:
            # Get performance for all riders
            riders = User.objects.filter(role=User.Role.DELIVERY_RIDER, is_active=True)
            performances = []
            for rider in riders:
                perf = RiderPerformanceService.get_rider_performance(rider.id)
                performances.append(perf)
            return Response(performances)


class DeliveryZoneViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing delivery zones (Admin only)
    """
    queryset = DeliveryZone.objects.all()
    serializer_class = DeliveryZoneSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @extend_schema(summary="لیست مناطق تحویل")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(summary="ایجاد منطقه تحویل جدید")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @extend_schema(summary="ویرایش منطقه تحویل")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    @extend_schema(summary="حذف منطقه تحویل")
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class PeakTimeSettingViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing peak time settings (Admin only)
    """
    queryset = PeakTimeSetting.objects.all()
    serializer_class = PeakTimeSettingSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    @extend_schema(summary="لیست تنظیمات زمان شلوغی")
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)
    
    @extend_schema(summary="ایجاد تنظیمات زمان شلوغی")
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
    
    @extend_schema(summary="ویرایش تنظیمات زمان شلوغی")
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)
    
    