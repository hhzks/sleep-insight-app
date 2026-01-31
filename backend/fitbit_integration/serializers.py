"""
Fitbit Integration Serializers
"""
from rest_framework import serializers
from .models import FitbitToken, FitbitSyncLog


class FitbitAuthUrlSerializer(serializers.Serializer):
    """Serializer for Fitbit authorization URL response."""
    
    authorization_url = serializers.URLField()
    code_verifier = serializers.CharField()
    state = serializers.CharField()


class FitbitCallbackSerializer(serializers.Serializer):
    """Serializer for Fitbit OAuth callback."""
    
    code = serializers.CharField()
    code_verifier = serializers.CharField()
    state = serializers.CharField(required=False)


class FitbitConnectionStatusSerializer(serializers.Serializer):
    """Serializer for Fitbit connection status."""
    
    connected = serializers.BooleanField()
    fitbit_user_id = serializers.CharField(allow_blank=True)
    connected_at = serializers.DateTimeField(allow_null=True)
    last_sync = serializers.DateTimeField(allow_null=True)


class FitbitSyncSerializer(serializers.Serializer):
    """Serializer for Fitbit sync request."""
    
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    days = serializers.IntegerField(required=False, default=30, min_value=1, max_value=365)


class FitbitSyncLogSerializer(serializers.ModelSerializer):
    """Serializer for Fitbit sync logs."""
    
    class Meta:
        model = FitbitSyncLog
        fields = ['id', 'status', 'sync_date', 'records_synced', 'error_message', 'created_at']
