"""
Классы разрешений для разграничения доступа по ролям.
"""
from rest_framework import permissions
from .models import UserProfile


def get_user_role(user):
    """Возвращает роль пользователя или None для анонима."""
    if not user or not user.is_authenticated:
        return None
    try:
        return user.profile.role
    except (UserProfile.DoesNotExist, AttributeError):
        return UserProfile.ROLE_USER  # по умолчанию обычный пользователь


class IsAuthenticatedWithRole(permissions.BasePermission):
    """Требует аутентификации. Роль не проверяется."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated


class IsAdmin(permissions.BasePermission):
    """Доступ только для роли admin."""
    def has_permission(self, request, view):
        return get_user_role(request.user) == UserProfile.ROLE_ADMIN


class IsAdminOrBartender(permissions.BasePermission):
    """Доступ для admin и bartender."""
    def has_permission(self, request, view):
        role = get_user_role(request.user)
        return role in (UserProfile.ROLE_ADMIN, UserProfile.ROLE_BARTENDER)


class CanEditTapsContent(permissions.BasePermission):
    """Редактирование кранов (все поля кроме только видимости): admin и bartender."""
    def has_permission(self, request, view):
        role = get_user_role(request.user)
        return role in (UserProfile.ROLE_ADMIN, UserProfile.ROLE_BARTENDER)


class CanChangeTapVisibilityOnly(permissions.BasePermission):
    """Разрешено менять только видимость крана: user и выше."""
    def has_permission(self, request, view):
        role = get_user_role(request.user)
        return role in (UserProfile.ROLE_ADMIN, UserProfile.ROLE_USER)
