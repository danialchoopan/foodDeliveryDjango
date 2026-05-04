from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'delivery'

router = DefaultRouter()
router.register('tracking', views.DeliveryTrackingViewSet, basename='delivery-tracking')
router.register('location-history', views.RiderLocationHistoryViewSet, basename='location-history')
router.register('delivery-zones', views.DeliveryZoneViewSet, basename='delivery-zones')
router.register('peak-times', views.PeakTimeSettingViewSet, basename='peak-times')

urlpatterns = [
    path('', include(router.urls)),
    
    # Rider and fee endpoints
    path('nearby-riders/', views.NearbyRidersView.as_view(), name='nearby-riders'),
    path('calculate-fee/', views.DeliveryFeeView.as_view(), name='calculate-fee'),
    path('rider-performance/', views.RiderPerformanceView.as_view(), name='rider-performance'),
    path('rider-performance/<int:rider_id>/', views.RiderPerformanceView.as_view(), name='rider-performance-detail'),
]

