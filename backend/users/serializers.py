"""
User Serializers
"""
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'display_name', 'avatar_url', 'timezone',
            'target_sleep_hours', 'target_bedtime', 'target_waketime',
            'enable_sleep_reminders', 'reminder_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email', 'created_at', 'updated_at']


class UserPreferencesSerializer(serializers.ModelSerializer):
    """Serializer for updating user preferences."""
    
    class Meta:
        model = User
        fields = [
            'timezone', 'target_sleep_hours', 'target_bedtime', 
            'target_waketime', 'enable_sleep_reminders', 'reminder_time'
        ]
