"""
URLs для API приложения parser_app.
"""

from django.urls import path, include
from django.views.decorators.csrf import csrf_exempt
from rest_framework.routers import DefaultRouter
from .views import (
    FileViewSet, ParsedItemViewSet, OrderViewSet, SupplierViewSet, upload_file,
    TapLocationViewSet, TapViewSet, AvailableBeerViewSet, UserViewSet,
    ParseRunViewSet, ParsingFeedbackViewSet, SupplierColumnMappingViewSet,
)
from . import auth_views

router = DefaultRouter()
router.register(r'files', FileViewSet, basename='file')
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'items', ParsedItemViewSet, basename='item')
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'locations', TapLocationViewSet, basename='location')
router.register(r'taps', TapViewSet, basename='tap')
router.register(r'available-beers', AvailableBeerViewSet, basename='available-beer')
router.register(r'users', UserViewSet, basename='user')
router.register(r'parse-runs', ParseRunViewSet, basename='parse-run')
router.register(r'column-mappings', SupplierColumnMappingViewSet, basename='column-mapping')
router.register(r'parsing-feedback', ParsingFeedbackViewSet, basename='parsing-feedback')

urlpatterns = [
    path('auth/login/', csrf_exempt(auth_views.AuthLoginView.as_view()), name='auth-login'),
    path('auth/logout/', auth_views.AuthLogoutView.as_view(), name='auth-logout'),
    path('auth/me/', auth_views.auth_me, name='auth-me'),
    path('upload/', upload_file, name='upload'),
    path('', include(router.urls)),
]

