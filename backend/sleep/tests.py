"""
Tests for sleep records.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import SleepRecord

User = get_user_model()


def night(user, days_ago, **overrides):
    """Build kwargs for a sleep record starting `days_ago` nights back."""
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
    }
    data.update(overrides)
    return data


class ManualSleepRecordTests(TestCase):
    """Manual entries carry no external ID, so they must not collide."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    def test_user_can_store_multiple_manual_records(self):
        SleepRecord.objects.create(**night(self.user, 1))
        SleepRecord.objects.create(**night(self.user, 2))

        self.assertEqual(SleepRecord.objects.filter(user=self.user).count(), 2)

    def test_api_accepts_more_than_one_manual_entry(self):
        client = APIClient()
        client.force_authenticate(user=self.user)

        for days_ago in (1, 2):
            end = timezone.now() - timedelta(days=days_ago)
            response = client.post('/api/sleep/records/', {
                'date_of_sleep': end.date().isoformat(),
                'start_time': (end - timedelta(hours=8)).isoformat(),
                'end_time': end.isoformat(),
                'quality_rating': 4,
            }, format='json')
            self.assertEqual(response.status_code, 201, response.content)

        self.assertEqual(SleepRecord.objects.filter(user=self.user).count(), 2)


class ExternalIdUniquenessTests(TestCase):
    """The constraint still has to keep Fitbit sync idempotent."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    def test_duplicate_external_id_is_rejected_for_same_user(self):
        SleepRecord.objects.create(**night(self.user, 1, source='fitbit', external_id='log-42'))

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SleepRecord.objects.create(
                    **night(self.user, 2, source='fitbit', external_id='log-42')
                )

    def test_same_external_id_allowed_across_different_users(self):
        other = User.objects.create(email='other@example.com', firebase_uid='uid-2')

        SleepRecord.objects.create(**night(self.user, 1, source='fitbit', external_id='log-42'))
        SleepRecord.objects.create(**night(other, 1, source='fitbit', external_id='log-42'))

        self.assertEqual(SleepRecord.objects.filter(external_id='log-42').count(), 2)

    def test_fitbit_resync_updates_the_existing_record(self):
        SleepRecord.objects.create(**night(self.user, 1, source='fitbit', external_id='log-42'))

        SleepRecord.objects.update_or_create(
            user=self.user,
            external_id='log-42',
            defaults={'minutes_asleep': 400},
        )

        records = SleepRecord.objects.filter(user=self.user, external_id='log-42')
        self.assertEqual(records.count(), 1)
        self.assertEqual(records.first().minutes_asleep, 400)
