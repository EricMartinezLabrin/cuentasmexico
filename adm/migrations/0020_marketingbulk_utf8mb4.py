from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0019_marketingbulkwhatsapp'),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                'ALTER TABLE `adm_marketingbulkwhatsapp` '
                'CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; '
                'ALTER TABLE `adm_marketingbulkwhatsapprecipient` '
                'CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;'
            ),
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
