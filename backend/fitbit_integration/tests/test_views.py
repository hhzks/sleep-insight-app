"""
Tests for the Fitbit API endpoints.

The sync endpoint's contract is pinned here because its body was moved out
into sync.py: the response shape callers already depend on must survive.
"""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from fitbit_integration.models import FitbitSyncLog, FitbitToken
from fitbit_integration.services import FitbitAuthError, FitbitUnavailable
from fitbit_integration.sync import SyncOutcome
from sleep.models import SleepRecord

User = get_user_model()


class SyncEndpointTests(TestCase):
    """POST /api/fitbit/sync/"""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        FitbitToken.objects.create(
            user=self.user,
            access_token='access-1',
            refresh_token='refresh-1',
            expires_at=timezone.now() + timedelta(hours=8),
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        self.assertEqual(APIClient().post('/api/fitbit/sync/', {}, format='json').status_code, 401)

    @patch('fitbit_integration.views.sync_user_sleep')
    def test_reports_how_many_records_were_synced(self, mock_sync):
        end = timezone.now().date()
        mock_sync.return_value = SyncOutcome(
            records_synced=4, start_date=end - timedelta(days=30), end_date=end,
        )

        response = self.client.post('/api/fitbit/sync/', {'days': 30}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['records_synced'], 4)
        self.assertIn('date_range', response.data)

    @patch('fitbit_integration.views.sync_user_sleep')
    def test_days_argument_sets_the_window(self, mock_sync):
        end = timezone.now().date()
        mock_sync.return_value = SyncOutcome(
            records_synced=0, start_date=end - timedelta(days=7), end_date=end,
        )

        self.client.post('/api/fitbit/sync/', {'days': 7}, format='json')

        _, start_date, end_date = mock_sync.call_args.args
        self.assertEqual(end_date - start_date, timedelta(days=7))

    def test_rejects_an_out_of_range_window(self):
        response = self.client.post('/api/fitbit/sync/', {'days': 9999}, format='json')
        self.assertEqual(response.status_code, 400)

    @patch('fitbit_integration.views.sync_user_sleep', side_effect=FitbitUnavailable('503 down'))
    def test_reports_a_failed_sync(self, mock_sync):
        response = self.client.post('/api/fitbit/sync/', {'days': 30}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('503 down', response.data['error'])

    @patch('fitbit_integration.views.sync_user_sleep', side_effect=FitbitAuthError('invalid_grant'))
    def test_reports_dead_authorisation(self, mock_sync):
        response = self.client.post('/api/fitbit/sync/', {'days': 30}, format='json')
        self.assertEqual(response.status_code, 400)

    @patch('fitbit_integration.sync.FitbitService.get_sleep_log_range')
    def test_writes_records_end_to_end(self, mock_range):
        # One test that does not stub sync_user_sleep, so the wiring between
        # view and service is exercised rather than asserted about.
        mock_range.return_value = {'sleep': [{
            'logId': '2002', 'dateOfSleep': '2026-09-01',
            'startTime': '2026-09-01T23:00:00.000Z', 'endTime': '2026-09-02T07:00:00.000Z',
            'duration': 28800000, 'minutesAsleep': 450, 'minutesAwake': 30,
            'efficiency': 94, 'isMainSleep': True, 'type': 'stages', 'levels': {},
        }]}

        response = self.client.post('/api/fitbit/sync/', {'days': 30}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['records_synced'], 1)
        self.assertTrue(SleepRecord.objects.filter(user=self.user, external_id='2002').exists())
        self.assertEqual(FitbitSyncLog.objects.get(user=self.user).status, 'success')


class ConnectionStatusTests(TestCase):
    """GET/PATCH /api/fitbit/status/"""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def connect(self, auto_sync=True):
        return FitbitToken.objects.create(
            user=self.user,
            access_token='access-1',
            refresh_token='refresh-1',
            expires_at=timezone.now() + timedelta(hours=8),
            auto_sync=auto_sync,
        )

    def test_status_reports_auto_sync(self):
        self.connect(auto_sync=False)
        response = self.client.get('/api/fitbit/status/')

        self.assertTrue(response.data['connected'])
        self.assertFalse(response.data['auto_sync'])

    def test_disconnected_user_is_not_auto_synced(self):
        response = self.client.get('/api/fitbit/status/')

        self.assertFalse(response.data['connected'])
        self.assertFalse(response.data['auto_sync'])

    def test_auto_sync_can_be_turned_off(self):
        token = self.connect()

        response = self.client.patch('/api/fitbit/status/', {'auto_sync': False}, format='json')

        self.assertEqual(response.status_code, 200)
        token.refresh_from_db()
        self.assertFalse(token.auto_sync)

    def test_auto_sync_can_be_turned_back_on(self):
        token = self.connect(auto_sync=False)

        self.client.patch('/api/fitbit/status/', {'auto_sync': True}, format='json')

        token.refresh_from_db()
        self.assertTrue(token.auto_sync)

    def test_response_reflects_the_new_setting(self):
        self.connect()
        response = self.client.patch('/api/fitbit/status/', {'auto_sync': False}, format='json')
        self.assertFalse(response.data['auto_sync'])

    def test_cannot_set_auto_sync_without_connecting(self):
        response = self.client.patch('/api/fitbit/status/', {'auto_sync': True}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_rejects_a_non_boolean(self):
        self.connect()
        response = self.client.patch('/api/fitbit/status/', {'auto_sync': 'maybe'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_patch_requires_authentication(self):
        response = APIClient().patch('/api/fitbit/status/', {'auto_sync': True}, format='json')
        self.assertEqual(response.status_code, 401)
