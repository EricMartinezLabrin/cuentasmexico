# Generated by Django 4.2 on 2023-05-12 00:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0007_userdetail_token_alter_account_created_at'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='business',
            name='mp_customer_key',
        ),
        migrations.RemoveField(
            model_name='business',
            name='mp_secret_key',
        ),
        migrations.AddField(
            model_name='business',
            name='flow_customer_key',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='business',
            name='flow_secret_key',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='business',
            name='flow_show',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='business',
            name='stripe_customer_key',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='business',
            name='stripe_sandbox',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='business',
            name='stripe_secret_key',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

