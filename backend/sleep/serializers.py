"""
Sleep Serializers
"""
from rest_framework import serializers
from .models import SleepRecord, SleepStageData, SleepGoal


class SleepStageDataSerializer(serializers.ModelSerializer):
    """Serializer for sleep stage data."""
    
    class Meta:
        model = SleepStageData
        fields = ['id', 'stage', 'start_time', 'duration_seconds']
        read_only_fields = ['id']


class SleepRecordSerializer(serializers.ModelSerializer):
    """Serializer for sleep records."""
    
    stage_data = SleepStageDataSerializer(many=True, read_only=True)
    duration_hours = serializers.ReadOnlyField()
    sleep_hours = serializers.ReadOnlyField()
    
    class Meta:
        model = SleepRecord
        fields = [
            'id', 'date_of_sleep', 'start_time', 'end_time',
            'duration_minutes', 'minutes_asleep', 'minutes_awake',
            'efficiency', 'deep_sleep_minutes', 'light_sleep_minutes',
            'rem_sleep_minutes', 'quality_rating', 'sleep_type', 'source',
            'is_main_sleep', 'notes', 'caffeine_intake', 'alcohol_intake',
            'exercise_today', 'stress_level', 'duration_hours', 'sleep_hours',
            'stage_data', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'source', 'external_id', 'created_at', 'updated_at']


class SleepRecordCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating sleep records manually."""
    
    class Meta:
        model = SleepRecord
        fields = [
            'date_of_sleep', 'start_time', 'end_time',
            'quality_rating', 'notes', 'caffeine_intake',
            'alcohol_intake', 'exercise_today', 'stress_level'
        ]
    
    def create(self, validated_data):
        """Create a sleep record with calculated fields."""
        user = self.context['request'].user
        
        # Calculate duration
        start = validated_data['start_time']
        end = validated_data['end_time']
        duration = (end - start).total_seconds() / 60  # in minutes
        
        # Estimate awake time (assume 5% for manual entries)
        estimated_awake = int(duration * 0.05)
        
        sleep_record = SleepRecord.objects.create(
            user=user,
            duration_minutes=int(duration),
            minutes_asleep=int(duration - estimated_awake),
            minutes_awake=estimated_awake,
            efficiency=95,  # Estimated
            source='manual',
            **validated_data
        )
        
        return sleep_record


class SleepGoalSerializer(serializers.ModelSerializer):
    """Serializer for sleep goals."""
    
    class Meta:
        model = SleepGoal
        fields = [
            'id', 'target_hours', 'target_bedtime', 'target_waketime',
            'min_sleep_hours_weekly', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SleepStatisticsSerializer(serializers.Serializer):
    """Serializer for sleep statistics."""
    
    period = serializers.CharField()
    total_records = serializers.IntegerField()
    avg_duration_hours = serializers.FloatField()
    avg_sleep_hours = serializers.FloatField()
    avg_efficiency = serializers.FloatField()
    avg_quality_rating = serializers.FloatField(allow_null=True)
    avg_deep_sleep_minutes = serializers.FloatField(allow_null=True)
    avg_rem_sleep_minutes = serializers.FloatField(allow_null=True)
    avg_light_sleep_minutes = serializers.FloatField(allow_null=True)
    total_sleep_hours = serializers.FloatField()
    best_sleep_date = serializers.DateField(allow_null=True)
    worst_sleep_date = serializers.DateField(allow_null=True)
