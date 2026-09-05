"""
The scheduled sync: one fan-out task that dispatches one task per user.
"""
from datetime import timedelta
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from fitbit_integration.models import FitbitToken
from fitbit_integration.services import FitbitAuthError, FitbitUnavailable
from fitbit_integration.sync import SyncOutcome
from fitbit_integration.tasks import sync_all_users_task, sync_user_task
from sleep_tracker.celery import app

User = get_user_model()


def connected_user(email, uid, auto_sync=True):
    user = User.objects.create(email=email, firebase_uid=uid)
    FitbitToken.objects.create(
        user=user,
        access_token='access-1',
        refresh_token='refresh-1',
        expires_at=timezone.now() + timedelta(hours=8),
        auto_sync=auto_sync,
    )
    return user


class TaskRegistrationTests(TestCase):
    def test_registered_under_stable_names(self):
        # Queued messages name their task, so a rename strands whatever is
        # already in the broker.
        self.assertEqual(sync_all_users_task.name, 'fitbit_integration.sync_all_users')
        self.assertEqual(sync_user_task.name, 'fitbit_integration.sync_user')


class BeatScheduleTests(TestCase):
    def test_nightly_sync_is_scheduled(self):
        entry = settings.CELERY_BEAT_SCHEDULE['nightly-fitbit-sync']
        self.assertEqual(entry['task'], 'fitbit_integration.sync_all_users')

        # Checking the registry too: settings and tasks.py could drift to the
        # same wrong string, or autodiscovery could stop finding tasks.py,
        # and a name comparison alone would still pass.
        self.assertIn(entry['task'], app.tasks)


class FanOutTests(TestCase):
    """Who the nightly run picks up."""

    @patch('fitbit_integration.tasks.sync_user_task.delay')
    def test_dispatches_one_task_per_connected_user(self, mock_delay):
        connected_user('a@example.com', 'uid-a')
        connected_user('b@example.com', 'uid-b')

        sync_all_users_task.apply()

        self.assertEqual(mock_delay.call_count, 2)

    @patch('fitbit_integration.tasks.sync_user_task.delay')
    def test_skips_users_who_turned_auto_sync_off(self, mock_delay):
        wanted = connected_user('a@example.com', 'uid-a')
        connected_user('b@example.com', 'uid-b', auto_sync=False)

        sync_all_users_task.apply()

        mock_delay.assert_called_once_with(wanted.pk)

    @patch('fitbit_integration.tasks.sync_user_task.delay')
    def test_ignores_users_who_never_connected_fitbit(self, mock_delay):
        User.objects.create(email='c@example.com', firebase_uid='uid-c')

        sync_all_users_task.apply()

        mock_delay.assert_not_called()

    @patch('fitbit_integration.tasks.sync_user_task.delay')
    def test_reports_how_many_users_were_dispatched(self, mock_delay):
        connected_user('a@example.com', 'uid-a')
        self.assertEqual(sync_all_users_task.apply().get(), 1)


class PerUserSyncTests(TestCase):
    """What each dispatched task does."""

    def setUp(self):
        self.user = connected_user('a@example.com', 'uid-a')

    @patch('fitbit_integration.tasks.sync_user_sleep')
    def test_syncs_the_configured_lookback_window(self, mock_sync):
        today = timezone.now().date()
        mock_sync.return_value = SyncOutcome(1, today, today)

        sync_user_task.apply(args=[self.user.pk])

        user, start_date, end_date = mock_sync.call_args.args
        self.assertEqual(user, self.user)
        self.assertEqual(end_date, today)
        self.assertEqual((end_date - start_date).days, settings.FITBIT_SYNC_LOOKBACK_DAYS)

    @patch('fitbit_integration.tasks.sync_user_sleep')
    def test_reports_records_synced(self, mock_sync):
        today = timezone.now().date()
        mock_sync.return_value = SyncOutcome(4, today, today)

        self.assertEqual(sync_user_task.apply(args=[self.user.pk]).get(), 4)

    @patch('fitbit_integration.tasks.sync_user_sleep', side_effect=FitbitUnavailable('503'))
    def test_a_failing_user_does_not_fail_the_task(self, mock_sync):
        # Each user gets their own task, and the failure is already in their
        # sync log. Raising here would only add retry noise for a run that
        # will come round again tomorrow.
        result = sync_user_task.apply(args=[self.user.pk])

        self.assertTrue(result.successful())
        self.assertEqual(result.get(), 0)

    @patch('fitbit_integration.tasks.sync_user_sleep', side_effect=FitbitAuthError('invalid_grant'))
    def test_dead_authorisation_does_not_fail_the_task(self, mock_sync):
        result = sync_user_task.apply(args=[self.user.pk])
        self.assertTrue(result.successful())

    @patch('fitbit_integration.tasks.sync_user_sleep')
    def test_a_user_deleted_before_pickup_is_skipped(self, mock_sync):
        # The fan-out and the per-user task are separated by queue time.
        missing_pk = self.user.pk
        self.user.delete()

        result = sync_user_task.apply(args=[missing_pk])

        self.assertTrue(result.successful())
        mock_sync.assert_not_called()
