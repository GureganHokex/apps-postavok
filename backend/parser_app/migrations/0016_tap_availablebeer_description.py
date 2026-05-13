from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parser_app', '0015_parserun_suppliercolumnmapping_parsingfeedback_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='availablebeer',
            name='description',
            field=models.TextField(blank=True, default='', verbose_name='Описание кеги'),
        ),
        migrations.AddField(
            model_name='tap',
            name='description',
            field=models.TextField(blank=True, default='', verbose_name='Описание кеги'),
        ),
    ]
