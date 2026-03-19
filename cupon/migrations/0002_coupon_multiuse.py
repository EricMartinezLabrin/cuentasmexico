from django.db import migrations, models
import django.db.models.deletion
from django.db.models import Q, Case, When, Value, IntegerField, BooleanField, CharField


def migrate_legacy_coupon_data(apps, schema_editor):
    Cupon = apps.get_model('cupon', 'Cupon')

    Cupon.objects.all().update(
        duration_unit=Case(
            When(long=12, then=Value('year')),
            When(long=7, then=Value('week')),
            When(long__in=[365, 366], then=Value('year')),
            default=Value('month'),
            output_field=CharField(max_length=10),
        ),
        duration_quantity=Value(1),
        requires_duration_review=Case(
            When(long__in=[1, 7, 12, 30, 31, 365, 366], then=Value(False)),
            default=Value(True),
            output_field=BooleanField(),
        ),
        max_uses=Value(1),
        used_count=Case(
            When(Q(status=False) & (Q(customer_id__isnull=False) | Q(status_sale=True)), then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        ),
        one_use_per_phone=Value(True),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0011_accountchangehistory'),
        ('cupon', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='cupon',
            name='duration_quantity',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='cupon',
            name='duration_unit',
            field=models.CharField(choices=[('day', '1 día'), ('week', '1 semana'), ('month', '1 mes'), ('year', '1 año')], default='month', max_length=10),
        ),
        migrations.AddField(
            model_name='cupon',
            name='max_uses',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='cupon',
            name='one_use_per_phone',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='cupon',
            name='requires_duration_review',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='cupon',
            name='used_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='CouponRedemption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('channel', models.CharField(choices=[('web', 'Web'), ('admin', 'Admin')], max_length=10)),
                ('service_name', models.CharField(blank=True, max_length=120, null=True)),
                ('account_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('profile', models.IntegerField(blank=True, null=True)),
                ('payment_amount', models.IntegerField(blank=True, null=True)),
                ('duration_unit', models.CharField(choices=[('day', '1 día'), ('week', '1 semana'), ('month', '1 mes'), ('year', '1 año')], max_length=10)),
                ('duration_quantity', models.PositiveIntegerField(default=1)),
                ('phone_lada', models.IntegerField(blank=True, null=True)),
                ('phone_number', models.CharField(blank=True, max_length=20, null=True)),
                ('phone_key', models.CharField(blank=True, max_length=32, null=True)),
                ('redeemed_at', models.DateTimeField(auto_now_add=True)),
                ('cupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='redemptions', to='cupon.cupon')),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_redemptions', to='auth.user')),
                ('sale', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='coupon_redemptions', to='adm.sale')),
            ],
            options={
                'ordering': ['-redeemed_at'],
                'indexes': [
                    models.Index(fields=['cupon', 'redeemed_at'], name='cr_cupon_redeemed_idx'),
                    models.Index(fields=['phone_number'], name='cr_phone_num_idx'),
                    models.Index(fields=['redeemed_at'], name='cr_redeemed_idx'),
                    models.Index(fields=['phone_key'], name='cr_phone_key_idx'),
                ],
            },
        ),
        migrations.AddIndex(
            model_name='cupon',
            index=models.Index(fields=['status'], name='cupon_status_idx'),
        ),
        migrations.AddIndex(
            model_name='cupon',
            index=models.Index(fields=['used_count', 'max_uses'], name='cupon_uses_idx'),
        ),
        migrations.RunPython(migrate_legacy_coupon_data, migrations.RunPython.noop),
    ]
