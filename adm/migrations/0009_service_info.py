# Generated by Django 4.2 on 2023-05-12 22:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0008_remove_business_mp_customer_key_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='service',
            name='info',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]
