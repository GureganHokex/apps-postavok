"""
URLs для API приложения parser_app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FileViewSet, ParsedItemViewSet, OrderViewSet, SupplierViewSet, upload_file,
    TapLocationViewSet, TapViewSet, AvailableBeerViewSet
)

router = DefaultRouter()
router.register(r'files', FileViewSet, basename='file')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'items', ParsedItemViewSet, basename='item')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'locations', TapLocationViewSet, basename='location')
router.register(r'taps', TapViewSet, basename='tap')
router.register(r'available-beers', AvailableBeerViewSet, basename='available-beer')

urlpatterns = [
    path('upload/', upload_file, name='upload'),
    path('', include(router.urls)),
]

