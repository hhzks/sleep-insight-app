"""
Sleep Views
"""
from datetime import datetime, timedelta
from django.db.models import Avg, Sum, Min, Max
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import SleepRecord, SleepGoal
from .serializers import (
    SleepRecordSerializer,
    SleepRecordCreateSerializer,
    SleepGoalSerializer,
    SleepStatisticsSerializer
)


class SleepRecordViewSet(viewsets.ModelViewSet):
    """ViewSet for sleep records."""
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return sleep records for the current user."""
        queryset = SleepRecord.objects.filter(user=self.request.user)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date_of_sleep__gte=start_date)
        if end_date:
            queryset = queryset.filter(date_of_sleep__lte=end_date)
        
        # Filter by source
        source = self.request.query_params.get('source')
        if source:
            queryset = queryset.filter(source=source)
        
        # Filter by main sleep only
        main_only = self.request.query_params.get('main_only', 'true').lower() == 'true'
        if main_only:
            queryset = queryset.filter(is_main_sleep=True)
        
        return queryset.prefetch_related('stage_data')
    
    def get_serializer_class(self):
        """Return appropriate serializer."""
        if self.action == 'create':
            return SleepRecordCreateSerializer
        return SleepRecordSerializer
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get sleep statistics for a period."""
        period = request.query_params.get('period', '30')  # days
        
        try:
            days = int(period)
        except ValueError:
            days = 30
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        records = SleepRecord.objects.filter(
            user=request.user,
            date_of_sleep__gte=start_date,
            date_of_sleep__lte=end_date,
            is_main_sleep=True
        )
        
        stats = records.aggregate(
            avg_duration=Avg('duration_minutes'),
            avg_asleep=Avg('minutes_asleep'),
            avg_efficiency=Avg('efficiency'),
            avg_quality=Avg('quality_rating'),
            avg_deep=Avg('deep_sleep_minutes'),
            avg_rem=Avg('rem_sleep_minutes'),
            avg_light=Avg('light_sleep_minutes'),
            total_sleep=Sum('minutes_asleep'),
        )
        
        # Get best and worst sleep
        best_sleep = records.order_by('-efficiency', '-minutes_asleep').first()
        worst_sleep = records.order_by('efficiency', 'minutes_asleep').first()
        
        data = {
            'period': f'{days} days',
            'total_records': records.count(),
            'avg_duration_hours': round((stats['avg_duration'] or 0) / 60, 2),
            'avg_sleep_hours': round((stats['avg_asleep'] or 0) / 60, 2),
            'avg_efficiency': round(stats['avg_efficiency'] or 0, 1),
            'avg_quality_rating': round(stats['avg_quality'], 1) if stats['avg_quality'] else None,
            'avg_deep_sleep_minutes': round(stats['avg_deep'], 1) if stats['avg_deep'] else None,
            'avg_rem_sleep_minutes': round(stats['avg_rem'], 1) if stats['avg_rem'] else None,
            'avg_light_sleep_minutes': round(stats['avg_light'], 1) if stats['avg_light'] else None,
            'total_sleep_hours': round((stats['total_sleep'] or 0) / 60, 2),
            'best_sleep_date': best_sleep.date_of_sleep if best_sleep else None,
            'worst_sleep_date': worst_sleep.date_of_sleep if worst_sleep else None,
        }
        
        serializer = SleepStatisticsSerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent sleep records (last 7 days)."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        
        records = SleepRecord.objects.filter(
            user=request.user,
            date_of_sleep__gte=start_date,
            is_main_sleep=True
        ).prefetch_related('stage_data')
        
        serializer = SleepRecordSerializer(records, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def trends(self, request):
        """Get sleep trends over time."""
        period = request.query_params.get('period', '30')
        
        try:
            days = int(period)
        except ValueError:
            days = 30
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        records = SleepRecord.objects.filter(
            user=request.user,
            date_of_sleep__gte=start_date,
            is_main_sleep=True
        ).order_by('date_of_sleep')
        
        trends = []
        for record in records:
            trends.append({
                'date': record.date_of_sleep,
                'sleep_hours': record.sleep_hours,
                'efficiency': record.efficiency,
                'quality_rating': record.quality_rating,
            })
        
        return Response(trends)


class SleepGoalViewSet(viewsets.ModelViewSet):
    """ViewSet for sleep goals."""
    
    serializer_class = SleepGoalSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return sleep goal for the current user."""
        return SleepGoal.objects.filter(user=self.request.user)
    
    def create(self, request, *args, **kwargs):
        """Create or update sleep goal."""
        goal, created = SleepGoal.objects.get_or_create(
            user=request.user,
            defaults=request.data
        )
        
        if not created:
            serializer = self.get_serializer(goal, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        
        serializer = self.get_serializer(goal)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'])
    def progress(self, request):
        """Get progress towards sleep goal."""
        try:
            goal = SleepGoal.objects.get(user=request.user)
        except SleepGoal.DoesNotExist:
            return Response({'error': 'No sleep goal set'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get this week's sleep
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday())
        
        records = SleepRecord.objects.filter(
            user=request.user,
            date_of_sleep__gte=week_start,
            is_main_sleep=True
        )
        
        total_sleep_minutes = records.aggregate(total=Sum('minutes_asleep'))['total'] or 0
        total_sleep_hours = total_sleep_minutes / 60
        
        avg_sleep = records.aggregate(avg=Avg('minutes_asleep'))['avg'] or 0
        avg_sleep_hours = avg_sleep / 60
        
        progress = {
            'goal': SleepGoalSerializer(goal).data,
            'weekly_progress': {
                'total_sleep_hours': round(total_sleep_hours, 2),
                'target_hours': goal.min_sleep_hours_weekly,
                'percentage': round((total_sleep_hours / goal.min_sleep_hours_weekly) * 100, 1) if goal.min_sleep_hours_weekly else 0,
            },
            'daily_average': {
                'avg_sleep_hours': round(avg_sleep_hours, 2),
                'target_hours': float(goal.target_hours),
                'percentage': round((avg_sleep_hours / float(goal.target_hours)) * 100, 1) if goal.target_hours else 0,
            },
            'days_tracked': records.count(),
        }
        
        return Response(progress)
