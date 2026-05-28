from django.contrib import admin

from .models import Baby, CareRecord


@admin.register(Baby)
class BabyAdmin(admin.ModelAdmin):
    list_display = ("name", "birth_date", "updated_at")


@admin.register(CareRecord)
class CareRecordAdmin(admin.ModelAdmin):
    list_display = ("baby", "record_type", "time", "note")
    list_filter = ("record_type", "pee", "poop")
    search_fields = ("note", "feed_amount", "symptom")
