from django.db import migrations, models
import django.core.validators


def validate_unique_phone_numbers(apps, schema_editor):
    UserDetail = apps.get_model('adm', 'UserDetail')
    duplicates = list(
        UserDetail.objects.values('phone_number')
        .annotate(total=models.Count('id'))
        .filter(phone_number__isnull=False)
        .filter(total__gt=1)
        .order_by('phone_number')[:20]
    )
    if duplicates:
        values = ', '.join(
            f"{item['phone_number']} ({item['total']})" for item in duplicates
        )
        raise RuntimeError(
            'No se puede aplicar unicidad de UserDetail.phone_number. '
            f'Duplicados detectados: {values}. '
            'Corrige los registros antes de ejecutar migrate.'
        )


def replace_placeholder_phone_numbers(apps, schema_editor):
    UserDetail = apps.get_model('adm', 'UserDetail')
    UserDetail.objects.filter(phone_number__in=['', '0']).update(phone_number=None)


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0014_wikisection'),
    ]

    operations = [
        migrations.AlterField(
            model_name='userdetail',
            name='phone_number',
            field=models.CharField(
                max_length=16,
                null=True,
                unique=False,
                validators=[django.core.validators.RegexValidator(regex='^\\+?1?\\d{8,15}$')],
            ),
        ),
        migrations.RunPython(replace_placeholder_phone_numbers, migrations.RunPython.noop),
        migrations.RunPython(validate_unique_phone_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='userdetail',
            name='phone_number',
            field=models.CharField(
                max_length=16,
                null=True,
                unique=True,
                validators=[django.core.validators.RegexValidator(regex='^\\+?1?\\d{8,15}$')],
            ),
        ),
    ]
