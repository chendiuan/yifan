from django.db import migrations


def remove_empty_growth_records(apps, schema_editor):
    CareRecord = apps.get_model("tracker", "CareRecord")
    CareRecord.objects.filter(
        record_type="growth",
        weight__isnull=True,
        height__isnull=True,
        note="",
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0003_alter_carerecord_weight"),
    ]

    operations = [
        migrations.RunPython(
            remove_empty_growth_records,
            migrations.RunPython.noop,
        ),
    ]
