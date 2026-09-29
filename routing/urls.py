from django.urls import path
from .views import RouteOptimizationView, RouteMapView

urlpatterns = [
    path('route/', RouteOptimizationView.as_view(), name='route_optimization'),
    path('route/map/', RouteMapView.as_view(), name='route_map'),
]
