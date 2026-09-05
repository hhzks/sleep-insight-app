from django.contrib import admin
from .models import FitbitToken, FitbitSyncLog


@admin.register(FitbitToken)
class FitbitTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'fitbit_user_id', 'expires_at', 'created_at']
    search_fields = ['user__email', 'fitbit_user_id']

    # The token columns are encrypted at rest, and the field decrypts on
    # read - so putting them anywhere on this page would hand the plaintext
    # to every staff user and undo the point of encrypting them. Support
    # needs to know who is connected and whether the grant is current,
    # which the remaining fields already answer.
    exclude = ['access_token', 'refresh_token']


@admin.register(FitbitSyncLog)
class FitbitSyncLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'status', 'sync_date', 'records_synced', 'created_at']
    search_fields = ['user__email']
    list_filter = ['status', 'sync_date']
