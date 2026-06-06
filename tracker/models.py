from django.db import models


class Baby(models.Model):
    name = models.CharField(max_length=80, default="依杋")
    birth_date = models.DateField(default="2026-05-18")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class CareRecord(models.Model):
    FEEDING = "feeding"
    SLEEP = "sleep"
    DIAPER = "diaper"
    HEALTH = "health"
    GROWTH = "growth"
    NOTE = "note"

    RECORD_TYPES = [
        (FEEDING, "餵食"),
        (SLEEP, "睡眠"),
        (DIAPER, "尿布"),
        (HEALTH, "健康"),
        (GROWTH, "成長"),
        (NOTE, "備註"),
    ]

    baby = models.ForeignKey(Baby, on_delete=models.CASCADE, related_name="records")
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    time = models.DateTimeField()
    note = models.TextField(blank=True)

    feed_kind = models.CharField(max_length=40, blank=True)
    feed_amount = models.CharField(max_length=80, blank=True)
    sleep_minutes = models.PositiveIntegerField(null=True, blank=True)

    pee = models.BooleanField(default=False)
    poop = models.BooleanField(default=False)
    poop_amount = models.CharField(max_length=40, blank=True)
    poop_color = models.CharField(max_length=40, blank=True)

    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    symptom = models.CharField(max_length=120, blank=True)
    weight = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    height = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-time", "-created_at"]

    def __str__(self):
        return f"{self.get_record_type_display()} {self.time:%Y-%m-%d %H:%M}"
