from django.db import migrations
from django.db.models import Q, Case, When, Value, IntegerField, BooleanField, CharField


def backfill_coupon_data(apps, schema_editor):
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
        ('cupon', '0002_coupon_multiuse'),
    ]

    operations = [
        migrations.RunPython(backfill_coupon_data, migrations.RunPython.noop),
    ]
