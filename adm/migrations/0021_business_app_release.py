from django.core.validators import RegexValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0020_marketingbulk_utf8mb4'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='app_version',
            field=models.CharField(
                blank=True,
                default='',
                max_length=20,
                validators=[RegexValidator(message='Usa el formato MAJOR.MINOR.PATCH.', regex='^\\d+\\.\\d+\\.\\d+$')],
            ),
        ),
        migrations.AddField(
            model_name='business',
            name='app_update_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='business',
            name='app_release_notes',
            field=models.TextField(blank=True, default=''),
        ),
    ]
