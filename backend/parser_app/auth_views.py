"""
Эндпоинты авторизации: login, logout, me.
"""
import logging

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import get_user_role
from .models import UserProfile


class SessionAuthenticationNoCSRF(SessionAuthentication):
    """Сессия без проверки CSRF — для кросс-доменного logout из SPA."""

    def enforce_csrf(self, request):
        pass

logger = logging.getLogger(__name__)


def _user_response(user):
    """Формирует ответ с данными пользователя и флагом is_admin."""
    role = get_user_role(user)
    return {
        'user': {
            'id': user.id,
            'username': user.username,
            'role': role or UserProfile.ROLE_USER,
        },
        'is_admin': role == UserProfile.ROLE_ADMIN,
    }


class AuthLoginView(APIView):
    """
    POST /api/auth/login/
    Body: { "username": "...", "password": "..." }
    Устанавливает сессию, возвращает user и is_admin.
    authentication_classes = [] — отключаем проверку CSRF для кросс-доменного входа.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser, FormParser]

    def post(self, request):
        try:
            username = (request.data.get('username') or '').strip()
            password = request.data.get('password', '')

            if not username or not password:
                return Response(
                    {'error': 'Укажите username и password'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            django_request = getattr(request, '_request', request)
            user = authenticate(django_request, username=username, password=password)
            if user is None:
                return Response(
                    {'error': 'Неверный логин или пароль'},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            login(django_request, user)
            return Response(_user_response(user))
        except Exception as e:
            logger.exception('Ошибка при входе')
            detail = str(e) if settings.DEBUG else 'Внутренняя ошибка сервера'
            return Response(
                {'error': detail},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AuthLogoutView(APIView):
    """
    POST /api/auth/logout/
    Сбрасывает сессию. SessionAuthenticationNoCSRF — без проверки CSRF для SPA.
    """
    authentication_classes = [SessionAuthenticationNoCSRF]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        django_request = getattr(request, '_request', request)
        logout(django_request)
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def auth_me(request):
    """
    GET /api/auth/me/
    Возвращает текущего пользователя и роль.
    """
    return Response(_user_response(request.user))
