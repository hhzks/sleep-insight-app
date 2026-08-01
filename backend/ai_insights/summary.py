"""
Summarizes a user's recent sleep records into the stats dict that both the
model prompt and the rule-based fallback consume.
"""
import statistics
from datetime import timedelta

from django.db.models import Avg, Count
from django.utils import timezone

from sleep.models import SleepGoal, SleepRecord


def build_sleep_summary(user, days=30):
    """Return a stats dict for the user's last `days` days, or None if no data."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    records = SleepRecord.objects.filter(
        user=user,
        date_of_sleep__gte=start_date,
        is_main_sleep=True,
    ).order_by('date_of_sleep')

    if not records.exists():
        return None

    stats = records.aggregate(
        avg_duration=Avg('duration_minutes'),
        avg_asleep=Avg('minutes_asleep'),
        avg_efficiency=Avg('efficiency'),
        avg_deep=Avg('deep_sleep_minutes'),
        avg_rem=Avg('rem_sleep_minutes'),
        avg_light=Avg('light_sleep_minutes'),
        total_records=Count('id'),
    )

    # Consistency is derived from how much bedtime varies night to night.
    sleep_times = [
        record.start_time.hour + record.start_time.minute / 60
        for record in records
        if record.start_time
    ]

    consistency_score = 0
    if len(sleep_times) > 1:
        try:
            std_dev = statistics.stdev(sleep_times)
            consistency_score = max(0, 100 - (std_dev * 20))
        except statistics.StatisticsError:
            consistency_score = 50

    try:
        target_hours = float(SleepGoal.objects.get(user=user).target_hours)
    except SleepGoal.DoesNotExist:
        target_hours = 8.0

    recent_records = records.filter(date_of_sleep__gte=end_date - timedelta(days=7))
    older_records = records.filter(
        date_of_sleep__lt=end_date - timedelta(days=7),
        date_of_sleep__gte=end_date - timedelta(days=14),
    )
    recent_avg = recent_records.aggregate(avg=Avg('minutes_asleep'))['avg'] or 0
    older_avg = older_records.aggregate(avg=Avg('minutes_asleep'))['avg'] or 0

    trend = 'stable'
    if recent_avg > older_avg * 1.1:
        trend = 'improving'
    elif recent_avg < older_avg * 0.9:
        trend = 'declining'

    return {
        'period_days': days,
        'total_records': records.count(),
        'avg_sleep_hours': round((stats['avg_asleep'] or 0) / 60, 2),
        'avg_time_in_bed_hours': round((stats['avg_duration'] or 0) / 60, 2),
        'avg_efficiency': round(stats['avg_efficiency'] or 0, 1),
        'avg_deep_sleep_minutes': round(stats['avg_deep'] or 0, 0),
        'avg_rem_sleep_minutes': round(stats['avg_rem'] or 0, 0),
        'avg_light_sleep_minutes': round(stats['avg_light'] or 0, 0),
        'consistency_score': round(consistency_score, 1),
        'target_hours': target_hours,
        'sleep_debt_hours': round(
            max(0, (target_hours - (stats['avg_asleep'] or 0) / 60) * days / 7), 1
        ),
        'trend': trend,
    }
