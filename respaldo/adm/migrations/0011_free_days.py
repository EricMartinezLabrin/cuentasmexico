# Generated by Django 4.2 on 2023-05-17 12:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0010_account_renewal_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='free_days',
            field=models.IntegerField(default=7),
        ),
    ]
