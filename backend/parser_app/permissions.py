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
        user = request.user
        if not user or not user.is_authenticated:
            return False
        # Поддерживаем оба источника админ-доступа:
        # бизнес-роль в профиле и стандартные Django-флаги.
        return (
            get_user_role(user) == UserProfile.ROLE_ADMIN
            or bool(user.is_superuser)
            or bool(user.is_staff)
        )


class IsAdminOrBartender(permissions.BasePermission):
    """Доступ для admin и bartender."""
    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser or user.is_staff:
            return True
        role = get_user_role(request.user)
        return role in (UserProfile.ROLE_ADMIN, UserProfile.ROLE_BARTENDER)


class CanEditTapsContent(permissions.BasePermission):
    """Редактирование кранов (все поля, включая видимость на экране): admin и bartender."""
    def has_permission(self, request, view):
        role = get_user_role(request.user)
        return role in (UserProfile.ROLE_ADMIN, UserProfile.ROLE_BARTENDER)
