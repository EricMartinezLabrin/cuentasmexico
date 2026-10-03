from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0015_userdetail_phone_number_unique'),
        ('cupon', '0007_shop_payment_bank'),
    ]

    operations = [
        migrations.CreateModel(
            name='SupportErrorImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('object_key', models.CharField(max_length=500)),
                ('mime_type', models.CharField(max_length=100)),
                ('size_bytes', models.PositiveBigIntegerField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('customer', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_error_images_received', to='auth.user')),
                ('shop', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_error_images', to='cupon.shop')),
                ('worker', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='support_error_images_sent', to='auth.user')),
            ],
            options={
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['shop', 'created_at'], name='adm_support_shop_id_7f7cc5_idx'),
                    models.Index(fields=['customer', 'created_at'], name='adm_support_custome_1c1f3f_idx'),
                ],
            },
        ),
    ]
