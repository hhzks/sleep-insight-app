"""
AI Insights Serializers
"""
from rest_framework import serializers
from .models import SleepInsight, SleepTip


class SleepInsightSerializer(serializers.ModelSerializer):
    """Serializer for sleep insights."""
    
    class Meta:
        model = SleepInsight
        fields = [
            'id', 'insight_type', 'priority', 'title', 'content',
            'start_date', 'end_date', 'is_read', 'is_helpful', 'created_at'
        ]
        read_only_fields = ['id', 'insight_type', 'priority', 'title', 'content', 'start_date', 'end_date', 'created_at']


class SleepTipSerializer(serializers.ModelSerializer):
    """Serializer for sleep tips."""
    
    class Meta:
        model = SleepTip
        fields = ['id', 'category', 'title', 'content', 'short_tip']


class InsightFeedbackSerializer(serializers.Serializer):
    """Serializer for insight feedback."""
    
    is_helpful = serializers.BooleanField()
