# Generated by Django 4.1.2 on 2022-11-28 23:37

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('cupon', '0001_initial'),
    ]

    operations = [
        migrations.RenameField(
            model_name='cupon',
            old_name='update_date',
            new_name='create_date',
        ),
        migrations.AlterField(
            model_name='cupon',
            name='customer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='customer', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='cupon',
            name='order',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='adm.sale'),
        ),
        migrations.AlterField(
            model_name='cupon',
            name='seller',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='seller', to=settings.AUTH_USER_MODEL),
        ),
    ]