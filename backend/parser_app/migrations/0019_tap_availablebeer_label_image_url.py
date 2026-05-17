# Generated manually

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parser_app', '0018_availablebeer_sort_order'),
    ]

    operations = [
        migrations.AddField(
            model_name='tap',
            name='label_image_url',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Ссылка на изображение этикетки, например с Untappd',
                max_length=600,
                verbose_name='Обложка (URL)',
            ),
        ),
        migrations.AddField(
            model_name='availablebeer',
            name='label_image_url',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Ссылка на изображение этикетки (Untappd и т.п.)',
                max_length=600,
                verbose_name='Обложка (URL)',
            ),
        ),
    ]
