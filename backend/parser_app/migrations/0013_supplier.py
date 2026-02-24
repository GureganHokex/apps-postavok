# Generated manually for Supplier model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parser_app', '0012_alter_file_file_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='Supplier',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True, verbose_name='Название поставщика')),
                ('column_mapping', models.JSONField(blank=True, default=dict, verbose_name='Ключевые слова для колонок')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления')),
            ],
            options={
                'verbose_name': 'Поставщик (настройки маппинга)',
                'verbose_name_plural': 'Поставщики (настройки маппинга)',
                'ordering': ['name'],
            },
        ),
    ]
