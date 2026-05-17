"""
Обработчик исключений DRF: ответы API всегда JSON, без HTML-страницы Django при 500.
"""
from django.conf import settings
from django.db.utils import OperationalError, ProgrammingError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def custom_exception_handler(exc, context):
    """
    Ошибки схемы БД (нет колонки после pull) → JSON с подсказкой про migrate.
    Остальное — стандартный DRF; если DRF не обработал — краткий JSON 500 вместо HTML.
    """
    if isinstance(exc, (OperationalError, ProgrammingError)):
        detail = (
            'Ошибка базы данных: схема не совпадает с кодом (часто не выполнен '
            '`python manage.py migrate` после обновления). Остановите backend, '
            'выполните migrate в каталоге с manage.py и снова запустите сервер.'
        )
        payload = {'detail': detail}
        if settings.DEBUG:
            payload['technical'] = str(exc)[:1200]
        return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    response = drf_exception_handler(exc, context)
    if response is not None:
        return response

    payload = {'detail': 'Внутренняя ошибка сервера.'}
    if settings.DEBUG:
        payload['detail'] = f'{exc.__class__.__name__}: {exc}'
    return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
