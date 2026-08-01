"""
Sleep data summarization.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ai_insights.summary import build_sleep_summary
from sleep.models import SleepRecord

User = get_user_model()


def night(user, days_ago, **overrides):
    """Build a main-sleep record starting `days_ago` nights back."""
    end = timezone.now() - timedelta(days=days_ago)
    start = end - timedelta(hours=8)
    data = {
        'user': user,
        'date_of_sleep': end.date(),
        'start_time': start,
        'end_time': end,
        'duration_minutes': 480,
        'minutes_asleep': 456,
        'minutes_awake': 24,
        'efficiency': 95,
        'source': 'manual',
        'is_main_sleep': True,
    }
    data.update(overrides)
    return SleepRecord.objects.create(**data)


class BuildSleepSummaryTests(TestCase):
    """Summaries drive both the prompt and the rule-based fallback."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    def test_returns_none_without_records(self):
        self.assertIsNone(build_sleep_summary(self.user, 30))

    def test_averages_recent_records(self):
        for days_ago in range(1, 8):
            night(self.user, days_ago)
        result = build_sleep_summary(self.user, 30)
        self.assertEqual(result['total_records'], 7)
        self.assertAlmostEqual(result['avg_sleep_hours'], 7.6, places=1)
        self.assertEqual(result['period_days'], 30)

    def test_excludes_records_outside_the_window(self):
        night(self.user, 2)
        night(self.user, 100)
        self.assertEqual(build_sleep_summary(self.user, 30)['total_records'], 1)

    def test_defaults_target_hours_without_a_goal(self):
        night(self.user, 1)
        self.assertEqual(build_sleep_summary(self.user, 30)['target_hours'], 8.0)
