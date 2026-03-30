from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cupon', '0004_cupon_excluded_services'),
    ]

    operations = [
        migrations.AddField(
            model_name='cupon',
            name='image',
            field=models.ImageField(blank=True, null=True, upload_to='cupon/'),
        ),
    ]
