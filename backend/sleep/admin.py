from django.contrib import admin
from .models import SleepRecord, SleepStageData, SleepGoal


class SleepStageDataInline(admin.TabularInline):
    model = SleepStageData
    extra = 0


@admin.register(SleepRecord)
class SleepRecordAdmin(admin.ModelAdmin):
    list_display = ['user', 'date_of_sleep', 'duration_minutes', 'efficiency', 'source', 'created_at']
    search_fields = ['user__email']
    list_filter = ['source', 'sleep_type', 'date_of_sleep', 'created_at']
    inlines = [SleepStageDataInline]
    date_hierarchy = 'date_of_sleep'


@admin.register(SleepGoal)
class SleepGoalAdmin(admin.ModelAdmin):
    list_display = ['user', 'target_hours', 'target_bedtime', 'target_waketime']
    search_fields = ['user__email']
