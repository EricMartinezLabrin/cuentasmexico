# Generated by Django 4.1.2 on 2022-12-13 21:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cupon', '0004_shop_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='shop',
            name='image',
            field=models.FileField(blank=True, null=True, upload_to='shop/'),
        ),
    ]