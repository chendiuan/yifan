import re
from decimal import Decimal, InvalidOperation

from django.db import migrations


DECIMAL_PATTERN = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)")
FIELD_LIMITS = {
    "temperature": (4, 1),
    "weight": (5, 2),
    "height": (5, 1),
}


def normalize_decimal(value, max_digits, decimal_places):
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        number = Decimal(text)
    except InvalidOperation:
        match = DECIMAL_PATTERN.search(text)
        if not match:
            return None
        try:
            number = Decimal(match.group(0))
        except InvalidOperation:
            return None

    if not number.is_finite():
        return None

    max_integer_digits = max_digits - decimal_places
    max_value = Decimal(10) ** max_integer_digits
    if abs(number) >= max_value:
        return None

    return str(number)


def repair_invalid_decimal_values(apps, schema_editor):
    table = schema_editor.quote_name("tracker_carerecord")
    connection = schema_editor.connection

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT id, temperature, weight, height FROM {table}"
        )
        rows = cursor.fetchall()

        for record_id, temperature, weight, height in rows:
            values = {
                "temperature": temperature,
                "weight": weight,
                "height": height,
            }
            updates = {}

            for field_name, value in values.items():
                max_digits, decimal_places = FIELD_LIMITS[field_name]
                normalized = normalize_decimal(value, max_digits, decimal_places)
                if normalized != value and str(normalized) != str(value):
                    updates[field_name] = normalized

            if not updates:
                continue

            assignments = ", ".join(
                f"{schema_editor.quote_name(field_name)} = %s"
                for field_name in updates
            )
            cursor.execute(
                f"UPDATE {table} SET {assignments} WHERE id = %s",
                [*updates.values(), record_id],
            )


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            repair_invalid_decimal_values,
            migrations.RunPython.noop,
        ),
    ]
