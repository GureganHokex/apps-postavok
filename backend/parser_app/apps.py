from django.apps import AppConfig


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        from .models import UserProfile
        UserProfile.objects.get_or_create(user=instance, defaults={'role': UserProfile.ROLE_USER})


class ParserAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'parser_app'
    verbose_name = 'Парсер прайсов'

    def ready(self):
        from django.db.models.signals import post_save
        from django.contrib.auth import get_user_model
        post_save.connect(create_user_profile, sender=get_user_model())
