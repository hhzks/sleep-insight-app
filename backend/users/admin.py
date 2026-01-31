from django.contrib import admin
from .models import User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'display_name', 'firebase_uid', 'created_at']
    search_fields = ['email', 'display_name', 'firebase_uid']
    list_filter = ['created_at', 'enable_sleep_reminders']
    readonly_fields = ['firebase_uid', 'created_at', 'updated_at']
