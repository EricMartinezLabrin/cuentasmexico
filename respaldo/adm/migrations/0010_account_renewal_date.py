# Generated by Django 4.2 on 2023-05-17 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0009_service_info'),
    ]

    operations = [
        migrations.AddField(
            model_name='account',
            name='renewal_date',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]