from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('adm', '0014_wikisection'),
        ('cupon', '0006_shop_credit_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='shop',
            name='payment_bank',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='payment_shops',
                to='adm.bank',
            ),
        ),
    ]
