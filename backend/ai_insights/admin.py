from django.contrib import admin
from .models import SleepInsight, SleepTip


@admin.register(SleepInsight)
class SleepInsightAdmin(admin.ModelAdmin):
    list_display = ['user', 'insight_type', 'priority', 'title', 'is_read', 'created_at']
    search_fields = ['user__email', 'title', 'content']
    list_filter = ['insight_type', 'priority', 'is_read', 'created_at']


@admin.register(SleepTip)
class SleepTipAdmin(admin.ModelAdmin):
    list_display = ['category', 'title', 'is_active', 'order']
    search_fields = ['title', 'content']
    list_filter = ['category', 'is_active']
    list_editable = ['order', 'is_active']
