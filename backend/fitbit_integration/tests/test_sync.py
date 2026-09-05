"""
Tests for sync_user_sleep, the one place Fitbit sleep data is imported.

Both the manual "Sync now" button and the nightly scheduled run call this,
so the accounting here is what keeps the two consistent.
"""
from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from fitbit_integration.models import FitbitSyncLog, FitbitToken
from fitbit_integration.services import FitbitAuthError, FitbitUnavailable
from fitbit_integration.sync import sync_user_sleep
from sleep.models import SleepRecord, SleepStageData

User = get_user_model()


def sleep_payload(log_id='1001', date_of_sleep='2026-09-01', with_stages=True):
    """One night, shaped the way Fitbit's /sleep/date range endpoint returns it."""
    entry = {
        'logId': log_id,
        'dateOfSleep': date_of_sleep,
        'startTime': f'{date_of_sleep}T23:10:00.000Z',
        'endTime': f'{date_of_sleep}T07:20:00.000Z',
        'duration': 29400000,
        'minutesAsleep': 456,
        'minutesAwake': 34,
        'efficiency': 93,
        'isMainSleep': True,
        'type': 'stages',
        'levels': {
            'summary': {
                'deep': {'minutes': 78},
                'light': {'minutes': 264},
                'rem': {'minutes': 114},
            },
            'data': [
                {'level': 'deep', 'dateTime': f'{date_of_sleep}T23:10:00.000Z', 'seconds': 1800},
                {'level': 'light', 'dateTime': f'{date_of_sleep}T23:40:00.000Z', 'seconds': 3600},
            ] if with_stages else [],
        },
    }
    return {'sleep': [entry]}


class SyncSuccessTests(TestCase):
    """A healthy sync writes records and clears any failure history."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.token = FitbitToken.objects.create(
            user=self.user,
            access_token='access-1',
            refresh_token='refresh-1',
            expires_at=timezone.now() + timedelta(hours=8),
        )
        self.start = date(2026, 9, 1)
        self.end = date(2026, 9, 3)

    def run_sync(self, payload):
        with patch(
            'fitbit_integration.sync.FitbitService.get_sleep_log_range',
            return_value=payload,
        ):
            return sync_user_sleep(self.user, self.start, self.end)

    def test_writes_a_sleep_record(self):
        self.run_sync(sleep_payload())

        record = SleepRecord.objects.get(user=self.user)
        self.assertEqual(record.external_id, '1001')
        self.assertEqual(record.source, 'fitbit')
        self.assertEqual(record.minutes_asleep, 456)

    def test_reports_how_many_records_were_synced(self):
        outcome = self.run_sync(sleep_payload())
        self.assertEqual(outcome.records_synced, 1)

    def test_writes_stage_detail(self):
        self.run_sync(sleep_payload())
        record = SleepRecord.objects.get(user=self.user)
        self.assertEqual(SleepStageData.objects.filter(sleep_record=record).count(), 2)

    def test_logs_a_successful_sync(self):
        self.run_sync(sleep_payload())

        log = FitbitSyncLog.objects.get(user=self.user)
        self.assertEqual(log.status, 'success')
        self.assertEqual(log.records_synced, 1)
        self.assertEqual(log.sync_date, self.end)

    def test_resyncing_a_night_updates_it_rather_than_duplicating(self):
        # The nightly run deliberately re-reads the last few days, so the
        # same logId arrives repeatedly. The (user, external_id) constraint
        # means a second write must be an update, not an IntegrityError.
        self.run_sync(sleep_payload())
        revised = sleep_payload()
        revised['sleep'][0]['minutesAsleep'] = 470
        self.run_sync(revised)

        self.assertEqual(SleepRecord.objects.filter(user=self.user).count(), 1)
        self.assertEqual(SleepRecord.objects.get(user=self.user).minutes_asleep, 470)

    def test_resyncing_refreshes_stage_detail(self):
        # Fitbit revises a night's staging after the fact, and the nightly
        # run re-reads recent days precisely to pick that up. Writing stages
        # only on first import would freeze whatever arrived first.
        self.run_sync(sleep_payload())

        revised = sleep_payload()
        revised['sleep'][0]['levels']['data'] = [
            {'level': 'wake', 'dateTime': '2026-09-01T23:10:00.000Z', 'seconds': 600},
        ]
        self.run_sync(revised)

        record = SleepRecord.objects.get(user=self.user)
        stages = SleepStageData.objects.filter(sleep_record=record)
        self.assertEqual(stages.count(), 1)
        self.assertEqual(stages.first().stage, 'wake')

    def test_success_clears_earlier_auth_failures(self):
        self.token.consecutive_auth_failures = 2
        self.token.save()

        self.run_sync(sleep_payload())

        self.token.refresh_from_db()
        self.assertEqual(self.token.consecutive_auth_failures, 0)


class SyncFailureAccountingTests(TestCase):
    """Only dead authorisation counts towards disconnecting a user."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.token = FitbitToken.objects.create(
            user=self.user,
            access_token='access-1',
            refresh_token='refresh-1',
            expires_at=timezone.now() + timedelta(hours=8),
        )
        self.start = date(2026, 9, 1)
        self.end = date(2026, 9, 3)

    def run_failing_sync(self, exc):
        with patch(
            'fitbit_integration.sync.FitbitService.get_sleep_log_range',
            side_effect=exc,
        ):
            with self.assertRaises(type(exc)):
                sync_user_sleep(self.user, self.start, self.end)

    def test_auth_failure_is_counted(self):
        self.run_failing_sync(FitbitAuthError('invalid_grant'))

        self.token.refresh_from_db()
        self.assertEqual(self.token.consecutive_auth_failures, 1)

    def test_auth_failure_is_logged(self):
        self.run_failing_sync(FitbitAuthError('invalid_grant'))

        log = FitbitSyncLog.objects.get(user=self.user)
        self.assertEqual(log.status, 'failed')
        self.assertIn('invalid_grant', log.error_message)

    def test_outage_does_not_count_towards_disconnection(self):
        # Fitbit being down is not evidence about this user's authorisation.
        # Counting it would disconnect healthy accounts after three bad nights.
        self.run_failing_sync(FitbitUnavailable('503 down'))

        self.token.refresh_from_db()
        self.assertEqual(self.token.consecutive_auth_failures, 0)

    def test_reaching_the_limit_disconnects_the_user(self):
        self.token.consecutive_auth_failures = 2
        self.token.save()

        self.run_failing_sync(FitbitAuthError('invalid_grant'))

        self.assertFalse(FitbitToken.objects.filter(user=self.user).exists())

    def test_disconnection_explains_itself_in_the_sync_log(self):
        self.token.consecutive_auth_failures = 2
        self.token.save()

        self.run_failing_sync(FitbitAuthError('invalid_grant'))

        log = FitbitSyncLog.objects.get(user=self.user)
        self.assertIn('Reconnect Fitbit', log.error_message)

    def test_a_failure_short_of_the_limit_keeps_the_connection(self):
        self.run_failing_sync(FitbitAuthError('invalid_grant'))
        self.assertTrue(FitbitToken.objects.filter(user=self.user).exists())

    def test_no_pending_log_is_left_behind_by_an_unexpected_fault(self):
        # A 'pending' row nothing finishes would read as a sync still in
        # flight forever.
        with patch(
            'fitbit_integration.sync.FitbitService.get_sleep_log_range',
            side_effect=ValueError('malformed payload'),
        ):
            with self.assertRaises(ValueError):
                sync_user_sleep(self.user, self.start, self.end)

        self.assertEqual(FitbitSyncLog.objects.get(user=self.user).status, 'failed')
