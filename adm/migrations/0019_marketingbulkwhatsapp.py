from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('adm', '0018_business_receivable_whatsapp'),
    ]

    operations = [
        migrations.CreateModel(
            name='MarketingBulkWhatsApp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message_text', models.TextField(blank=True, default='')),
                ('image', models.ImageField(blank=True, null=True, upload_to='marketing/bulk-whatsapp/')),
                ('delay_min_minutes', models.PositiveIntegerField(default=2)),
                ('delay_max_minutes', models.PositiveIntegerField(default=5)),
                ('batch_size', models.PositiveIntegerField(default=5)),
                ('batch_pause_min_minutes', models.PositiveIntegerField(default=10)),
                ('batch_pause_max_minutes', models.PositiveIntegerField(default=15)),
                ('status', models.CharField(choices=[('queued', 'En cola'), ('running', 'Enviando'), ('waiting', 'En espera'), ('completed', 'Terminado'), ('cancelled', 'Cancelado'), ('failed', 'Fallido')], default='queued', max_length=20)),
                ('total_count', models.PositiveIntegerField(default=0)),
                ('sent_count', models.PositiveIntegerField(default=0)),
                ('ignored_count', models.PositiveIntegerField(default=0)),
                ('error_count', models.PositiveIntegerField(default=0)),
                ('attempt_count', models.PositiveIntegerField(default=0)),
                ('current_number', models.CharField(blank=True, default='', max_length=20)),
                ('status_message', models.CharField(blank=True, default='', max_length=255)),
                ('next_action_at', models.DateTimeField(blank=True, null=True)),
                ('pause_until', models.DateTimeField(blank=True, null=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='marketing_bulk_whatsapp_jobs', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at'], 'indexes': [models.Index(fields=['status', 'next_action_at'], name='adm_marketi_status_c348b2_idx'), models.Index(fields=['created_by', 'created_at'], name='adm_marketi_created_2e6baf_idx')]},
        ),
        migrations.CreateModel(
            name='MarketingBulkWhatsAppRecipient',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('original_value', models.CharField(max_length=120)),
                ('normalized_number', models.CharField(blank=True, default='', max_length=20)),
                ('status', models.CharField(choices=[('pending', 'Pendiente'), ('sent', 'Enviado'), ('ignored', 'Ignorado'), ('error', 'Error')], default='pending', max_length=20)),
                ('reason', models.TextField(blank=True, default='')),
                ('provider_response', models.TextField(blank=True, default='')),
                ('attempted_at', models.DateTimeField(blank=True, null=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='adm.marketingbulkwhatsapp')),
            ],
            options={'ordering': ['id'], 'indexes': [models.Index(fields=['job', 'status', 'id'], name='adm_marketi_job_id_f9948a_idx'), models.Index(fields=['job', 'normalized_number'], name='adm_marketi_job_id_bba8c8_idx')]},
        ),
    ]
