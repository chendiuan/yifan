from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0002_repair_invalid_decimal_values"),
    ]

    operations = [
        migrations.AlterField(
            model_name="carerecord",
            name="weight",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=6,
                null=True,
            ),
        ),
    ]
