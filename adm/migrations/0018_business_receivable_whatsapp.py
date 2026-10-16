from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0017_shoppaymentproof'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='receivable_pending_whatsapp_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='business',
            name='receivable_pending_whatsapp_last_sent_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
