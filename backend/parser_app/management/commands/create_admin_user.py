"""
Создаёт или обновляет пользователя-администратора из настроек ADMIN_USERNAME / ADMIN_PASSWORD.
Запуск: python manage.py create_admin_user
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from parser_app.models import UserProfile

User = get_user_model()


class Command(BaseCommand):
    help = 'Создаёт или обновляет администратора из ADMIN_USERNAME и ADMIN_PASSWORD'

    def handle(self, *args, **options):
        username = getattr(settings, 'ADMIN_USERNAME', 'admin')
        password = getattr(settings, 'ADMIN_PASSWORD', '')

        if not password and not settings.DEBUG:
            self.stderr.write(
                self.style.ERROR('В production задайте ADMIN_PASSWORD в переменных окружения.')
            )
            return

        if not password:
            password = 'admin'  # fallback только для DEBUG
            self.stdout.write(self.style.WARNING('Используется пароль по умолчанию (только для разработки).'))

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'is_staff': True,
                'is_superuser': False,
                'last_login': timezone.now(),
            },
        )
        user.set_password(password)
        user.is_staff = True
        user.save(update_fields=['password', 'is_staff'])

        profile, profile_created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': UserProfile.ROLE_ADMIN},
        )
        if profile.role != UserProfile.ROLE_ADMIN:
            profile.role = UserProfile.ROLE_ADMIN
            profile.save(update_fields=['role'])

        if created:
            self.stdout.write(self.style.SUCCESS(f'Создан администратор: {username}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Обновлён администратор: {username}'))
