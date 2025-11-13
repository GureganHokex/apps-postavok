"""
URLs для API приложения parser_app.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FileViewSet, ParsedItemViewSet, OrderViewSet, upload_file
)

router = DefaultRouter()
router.register(r'files', FileViewSet, basename='file')
router.register(r'items', ParsedItemViewSet, basename='item')
router.register(r'orders', OrderViewSet, basename='order')

urlpatterns = [
    path('upload/', upload_file, name='upload'),
    path('', include(router.urls)),
]

