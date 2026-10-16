from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0016_supporterrorimage'),
        ('cupon', '0007_shop_payment_bank'),
    ]

    operations = [
        migrations.CreateModel(
            name='ShopPaymentProof',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payment_method', models.CharField(max_length=10)),
                ('debt_amount', models.PositiveBigIntegerField()),
                ('oxxo_fee', models.PositiveIntegerField(default=0)),
                ('total', models.PositiveBigIntegerField()),
                ('object_key', models.CharField(max_length=500)),
                ('mime_type', models.CharField(max_length=100)),
                ('size_bytes', models.PositiveBigIntegerField()),
                ('whatsapp_status_code', models.PositiveIntegerField(blank=True, null=True)),
                ('whatsapp_accepted', models.BooleanField(default=False)),
                ('whatsapp_response', models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='payment_proofs', to='cupon.shop')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='shop_payment_proofs', to='auth.user')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['shop', 'created_at'], name='adm_shop_pay_shop_id_4a7c1a_idx'),
                    models.Index(fields=['user', 'created_at'], name='adm_shop_pay_user_id_7e7f2d_idx'),
                ],
            },
        ),
    ]
