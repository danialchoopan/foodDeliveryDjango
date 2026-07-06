"""
Delivery services for rider matching, distance calculation, and performance tracking
"""
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from geopy.distance import distance
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from apps.accounts.models import User
from apps.orders.models import Order
from .models import DeliveryTracking, RiderLocationHistory, DeliveryZone, PeakTimeSetting

logger = logging.getLogger(__name__)


class RiderMatchingService:
    """
    Service for finding and matching riders to orders
    """
    
    @classmethod
    def find_nearest_available_riders(
        cls, 
        latitude: float, 
        longitude: float, 
        radius_km: int = 5,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find nearest available riders within given radius
        
        Args:
            latitude: Reference latitude
            longitude: Reference longitude
            radius_km: Search radius in kilometers
            limit: Maximum number of riders to return
            
        Returns:
            List of rider dicts with distance information
        """
        # Get all available riders with valid location
        available_riders = User.objects.filter(
            role=User.Role.DELIVERY_RIDER,
            is_active=True,
            rider_status=User.RiderStatus.AVAILABLE,
            current_latitude__isnull=False,
            current_longitude__isnull=False,
            last_location_update__gte=timezone.now() - timedelta(minutes=5)  # Recent location
        )
        
        riders_with_distance = []
        reference_point = (latitude, longitude)
        
        for rider in available_riders:
            rider_point = (float(rider.current_latitude), float(rider.current_longitude))
            dist = distance(reference_point, rider_point).kilometers
            
            if dist <= radius_km:
                riders_with_distance.append({
                    'rider': rider,
                    'distance_km': round(dist, 2)
                })
        
        # Sort by distance and limit
        riders_with_distance.sort(key=lambda x: x['distance_km'])
        
        result = []
        for item in riders_with_distance[:limit]:
            result.append({
                'rider_id': item['rider'].id,
                'rider_name': item['rider'].get_full_name() or item['rider'].username,
                'phone_number': item['rider'].phone_number,
                'latitude': float(item['rider'].current_latitude),
                'longitude': float(item['rider'].current_longitude),
                'distance_km': item['distance_km'],
                'rider_status': item['rider'].rider_status,
                'last_location_update': item['rider'].last_location_update
            })
        
        logger.info(f"Found {len(result)} available riders within {radius_km}km")
        return result
    
    @classmethod
    def smart_order_matching(cls, order_id: int, radius_km: int = 5) -> Optional[int]:
        """
        Automatically find and assign best rider to an order
        
        Args:
            order_id: Order ID to match
            radius_km: Search radius for riders
            
        Returns:
            Rider ID if matched, None otherwise
        """
        from apps.orders.services import OrderAssignmentService
        
        try:
            order = Order.objects.get(id=order_id, status=Order.Status.READY, rider__isnull=True)
        except Order.DoesNotExist:
            logger.warning(f"Order {order_id} is not available for matching")
            return None
        
        # Get restaurant location
        restaurant_lat = float(order.restaurant.latitude)
        restaurant_lng = float(order.restaurant.longitude)
        
        # Find nearest riders
        nearby_riders = cls.find_nearest_available_riders(
            restaurant_lat, 
            restaurant_lng, 
            radius_km,
            limit=1
        )
        
        if not nearby_riders:
            logger.info(f"No riders found near restaurant for order {order_id}")
            return None
        
        best_rider_id = nearby_riders[0]['rider_id']
        
        # Assign the order
        from apps.orders.services import OrderAssignmentService
        assigned_order = OrderAssignmentService.assign_rider_to_order(order_id, best_rider_id)
        
        if assigned_order:
            logger.info(f"Auto-matched order {order_id} to rider {best_rider_id}")
            return best_rider_id
        
        return None


class DeliveryFeeCalculator:
    """
    Service for calculating dynamic delivery fees
    """
    
    @classmethod
    def calculate_fee(
        cls,
        restaurant_lat: float,
        restaurant_lng: float,
        customer_lat: float,
        customer_lng: float,
        base_fee: int = 5000,
        fee_per_km: int = 2000
    ) -> Dict[str, Any]:
        """
        Calculate delivery fee based on distance and peak time
        
        Returns:
            Dict with fee, distance, and applied multipliers
        """
        # Calculate distance
        restaurant_loc = (restaurant_lat, restaurant_lng)
        customer_loc = (customer_lat, customer_lng)
        dist_km = distance(restaurant_loc, customer_loc).kilometers
        
        # Base distance fee
        distance_fee = base_fee + (dist_km * fee_per_km)
        
        # Apply peak time multiplier
        peak_multiplier = cls._get_peak_time_multiplier()
        
        # Apply zone extra fee
        zone_extra = cls._get_zone_extra_fee(customer_lat, customer_lng)
        
        total_fee = (distance_fee * peak_multiplier) + zone_extra
        
        return {
            'distance_km': round(dist_km, 2),
            'distance_fee': round(distance_fee),
            'peak_multiplier': float(peak_multiplier),
            'zone_extra_fee': int(zone_extra),
            'delivery_fee': round(total_fee)
        }
    
    @classmethod
    def _get_peak_time_multiplier(cls) -> float:
        """Get current peak time multiplier based on day and hour"""
        now = timezone.now()
        current_hour = now.hour
        current_weekday = now.weekday()  # Monday=0, Sunday=6
        
        try:
            peak_setting = PeakTimeSetting.objects.filter(
                day_of_week=current_weekday,
                start_hour__lte=current_hour,
                end_hour__gt=current_hour,
                is_active=True
            ).first()
            
            if peak_setting:
                return float(peak_setting.multiplier)
        except Exception as e:
            logger.error(f"Error getting peak time multiplier: {e}")
        
        return 1.0
    
    @classmethod
    def _get_zone_extra_fee(cls, latitude: float, longitude: float) -> int:
        """Get extra fee based on delivery zone"""
        try:
            zones = DeliveryZone.objects.filter(is_active=True)
            
            for zone in zones:
                zone_center = (float(zone.center_latitude), float(zone.center_longitude))
                customer_loc = (latitude, longitude)
                dist = distance(zone_center, customer_loc).kilometers
                
                if dist <= float(zone.radius_km):
                    return int(zone.extra_fee)
        except Exception as e:
            logger.error(f"Error getting zone extra fee: {e}")
        
        return 0


class RiderPerformanceService:
    """
    Service for calculating rider performance metrics
    """
    
    @classmethod
    def get_rider_performance(cls, rider_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get performance metrics for a specific rider
        
        Args:
            rider_id: ID of the rider
            days: Number of days to look back
            
        Returns:
            Dictionary with performance metrics
        """
        start_date = timezone.now() - timedelta(days=days)
        
        # Get all completed deliveries for this rider
        completed_orders = Order.objects.filter(
            rider_id=rider_id,
            status=Order.Status.DELIVERED,
            delivered_at__gte=start_date
        )
        
        # Get tracking data for performance metrics
        trackings = DeliveryTracking.objects.filter(
            rider_id=rider_id,
            delivered_at__gte=start_date
        )
        
        total_deliveries = completed_orders.count()
        
        # Calculate average delivery time
        avg_time = trackings.aggregate(
            avg_time=Avg('time_to_delivery_minutes')
        )['avg_time'] or 0
        
        # Calculate total distance
        total_distance = trackings.aggregate(
            total_dist=Sum('distance_traveled_km')
        )['total_dist'] or 0
        
        # Get current status
        rider = User.objects.get(id=rider_id)
        
        return {
            'rider_id': rider_id,
            'rider_name': rider.get_full_name() or rider.username,
            'total_deliveries': total_deliveries,
            'completed_deliveries': total_deliveries,
            'cancelled_deliveries': Order.objects.filter(
                rider_id=rider_id,
                status=Order.Status.CANCELLED,
                created_at__gte=start_date
            ).count(),
            'average_delivery_time_minutes': round(avg_time, 2) if avg_time else 0,
            'total_distance_km': round(float(total_distance), 2),
            'current_status': rider.rider_status,
            'rating': cls._calculate_rider_rating(rider_id, completed_orders)
        }
    
    @classmethod
    def _calculate_rider_rating(cls, rider_id: int, completed_orders) -> float:
        """
        Calculate rider rating based on delivery time and customer feedback
        Placeholder - can be expanded with actual rating model
        """
        # This can be enhanced with a Rating model
        # For now, return default or calculate from order data
        if completed_orders.count() == 0:
            return 5.0
        
        # Example: rating based on on-time delivery percentage
        on_time_count = 0
        for order in completed_orders:
            if order.estimated_delivery_time and order.delivered_at:
                if order.delivered_at <= order.estimated_delivery_time:
                    on_time_count += 1
        
        on_time_percentage = on_time_count / completed_orders.count()
        
        # Convert to 1-5 scale (minimum 3.0)
        rating = 3.0 + (on_time_percentage * 2.0)
        
        return round(rating, 1)


class DeliveryTrackingService:
    """
    Service for managing delivery tracking
    """
    
    @classmethod
    def create_tracking(cls, order: Order, rider: User) -> DeliveryTracking:
        """
        Create a tracking record for an order
        """
        tracking, created = DeliveryTracking.objects.get_or_create(
            order=order,
            defaults={'rider': rider}
        )
        
        if not created and tracking.rider != rider:
            tracking.rider = rider
            tracking.save()
        
        logger.info(f"Created delivery tracking for order {order.order_number}")
        return tracking
    
    @classmethod
    def update_tracking_location(
        cls, 
        tracking_id: int, 
        latitude: float, 
        longitude: float,
        status: str = None
    ) -> Optional[DeliveryTracking]:
        """
        Update tracking with current location
        """
        try:
            tracking = DeliveryTracking.objects.get(id=tracking_id)
            
            if status:
                tracking.update_status(status, latitude, longitude)
            else:
                tracking.save()
            
            # Also record in history if needed
            cls._record_location_history(tracking.rider_id, latitude, longitude, tracking.order_id)
            
            return tracking
        except DeliveryTracking.DoesNotExist:
            logger.error(f"Tracking {tracking_id} not found")
            return None
    
    @classmethod
    def _record_location_history(cls, rider_id: int, latitude: float, longitude: float, order_id: int = None):
        """
        Record location in history table (simplified - can be called periodically)
        """
        try:
            # Only record every minute to avoid too many records
            last_record = RiderLocationHistory.objects.filter(
                rider_id=rider_id,
                recorded_at__gte=timezone.now() - timedelta(seconds=55)
            ).first()
            
            if not last_record:
                RiderLocationHistory.objects.create(
                    rider_id=rider_id,
                    latitude=latitude,
                    longitude=longitude,
                    active_order_id=order_id
                )
        except Exception as e:
            logger.error(f"Error recording location history: {e}")


def calculate_eta(
    origin_lat: float,
    origin_lng: float,
    dest_lat: float,
    dest_lng: float,
    average_speed_kmh: float = 30
) -> int:
    """
    Calculate estimated time of arrival in minutes
    
    Args:
        origin_lat: Start latitude
        origin_lng: Start longitude
        dest_lat: Destination latitude
        dest_lng: Destination longitude
        average_speed_kmh: Average riding speed in km/h
        
    Returns:
        Estimated minutes to destination
    """
    origin = (origin_lat, origin_lng)
    destination = (dest_lat, dest_lng)
    dist_km = distance(origin, destination).kilometers
    
    # Time in minutes
    time_minutes = (dist_km / average_speed_kmh) * 60
    
    return int(round(time_minutes))

