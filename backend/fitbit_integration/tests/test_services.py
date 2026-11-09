"""
Tests for the Google Health API service.

The scheduled sync has to tell "this user's authorisation is dead" apart
from "Google had a bad minute": the first counts towards disconnecting
them, the second must never touch that counter.
"""
from datetime import date, timedelta
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from fitbit_integration.models import FitbitToken
from fitbit_integration.services import (
    SLEEP_READ_SCOPE,
    FitbitAuthError,
    FitbitError,
    FitbitUnavailable,
    GoogleHealthService,
    parse_google_health_sleep,
)

User = get_user_model()


class FakeResponse:
    """Stands in for requests.Response."""

    def __init__(self, status_code=200, body=None, text=''):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError('No JSON object could be decoded')
        return self._body


def make_user(email='sleeper@example.com', uid='uid-1'):
    return User.objects.create(email=email, firebase_uid=uid)


def make_token(user, expires_in_hours=1):
    return FitbitToken.objects.create(
        user=user,
        access_token='access-1',
        refresh_token='refresh-1',
        expires_at=timezone.now() + timedelta(hours=expires_in_hours),
    )


def token_body(**extra):
    body = {
        'access_token': 'access-2',
        'expires_in': 3599,
        'token_type': 'Bearer',
        'scope': SLEEP_READ_SCOPE,
    }
    body.update(extra)
    return body


@override_settings(
    GOOGLE_HEALTH_CLIENT_ID='client-id',
    GOOGLE_HEALTH_CLIENT_SECRET='client-secret',
    GOOGLE_HEALTH_REDIRECT_URI='http://localhost:3000/fitbit/callback',
)
class AuthorizationUrlTests(TestCase):

    def test_asks_google_for_offline_sleep_access_with_pkce(self):
        url = GoogleHealthService().get_authorization_url('challenge', 'state-1')
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        self.assertEqual(parsed.netloc, 'accounts.google.com')
        self.assertEqual(params['scope'], SLEEP_READ_SCOPE)
        self.assertEqual(params['access_type'], 'offline')
        self.assertEqual(params['prompt'], 'consent')
        self.assertEqual(params['code_challenge'], 'challenge')
        self.assertEqual(params['code_challenge_method'], 'S256')
        self.assertEqual(params['state'], 'state-1')
        self.assertEqual(params['client_id'], 'client-id')


class ConnectTests(TestCase):
    """Finishing the OAuth flow."""

    def setUp(self):
        self.user = make_user()
        self.service = GoogleHealthService(user=self.user)

    @patch('fitbit_integration.services.requests.request')
    @patch('fitbit_integration.services.requests.post')
    def test_saves_tokens_and_health_user_id(self, mock_post, mock_request):
        mock_post.return_value = FakeResponse(body=token_body(refresh_token='refresh-2'))
        mock_request.return_value = FakeResponse(body={
            'name': 'users/me/identity', 'legacyUserId': 'A1B2C3',
            'healthUserId': '111111256096816351',
        })

        token = self.service.connect('code', 'verifier')

        self.assertEqual(token.access_token, 'access-2')
        self.assertEqual(token.refresh_token, 'refresh-2')
        self.assertEqual(token.fitbit_user_id, '111111256096816351')
        self.assertEqual(
            mock_request.call_args.args[1],
            'https://health.googleapis.com/v4/users/me/identity',
        )

    @patch('fitbit_integration.services.requests.post')
    def test_rejects_a_grant_without_sleep_scope(self, mock_post):
        # Google's consent screen lets the user untick individual scopes.
        mock_post.return_value = FakeResponse(body=token_body(
            refresh_token='refresh-2', scope='openid',
        ))

        with self.assertRaises(FitbitAuthError):
            self.service.connect('code', 'verifier')
        self.assertFalse(FitbitToken.objects.exists())

    @patch('fitbit_integration.services.requests.post')
    def test_rejects_a_grant_without_refresh_token(self, mock_post):
        # The nightly sync cannot work without one.
        mock_post.return_value = FakeResponse(body=token_body())

        with self.assertRaises(FitbitError):
            self.service.connect('code', 'verifier')
        self.assertFalse(FitbitToken.objects.exists())

    @patch('fitbit_integration.services.requests.request')
    @patch('fitbit_integration.services.requests.post')
    def test_account_without_health_profile_is_not_connected(self, mock_post, mock_request):
        mock_post.return_value = FakeResponse(body=token_body(refresh_token='refresh-2'))
        mock_request.return_value = FakeResponse(status_code=400, body={'error': {
            'code': 400, 'status': 'FAILED_PRECONDITION',
            'details': [{'reason': 'ACCOUNT_NOT_LINKED'}],
        }})

        with self.assertRaisesMessage(FitbitAuthError, 'no Google Health profile'):
            self.service.connect('code', 'verifier')
        self.assertFalse(FitbitToken.objects.exists())

    @patch('fitbit_integration.services.requests.post')
    def test_failed_code_exchange_raises(self, mock_post):
        mock_post.return_value = FakeResponse(status_code=400, text='invalid_grant')

        with self.assertRaises(FitbitError):
            self.service.connect('code', 'verifier')


class TokenRefreshTests(TestCase):
    """A rejected refresh means the user must reconnect."""

    def setUp(self):
        self.user = make_user()

    def test_missing_token_raises_auth_error(self):
        service = GoogleHealthService(user=self.user)
        with self.assertRaises(FitbitAuthError):
            service.get_valid_access_token()

    @patch('fitbit_integration.services.requests.post')
    def test_refresh_keeps_the_stored_refresh_token(self, mock_post):
        # Google's refresh response usually carries no refresh_token. The
        # stored one stays valid and must not be lost.
        make_token(self.user, expires_in_hours=-1)
        mock_post.return_value = FakeResponse(body=token_body())

        access = GoogleHealthService(user=self.user).get_valid_access_token()

        self.assertEqual(access, 'access-2')
        self.assertEqual(FitbitToken.objects.get(user=self.user).refresh_token, 'refresh-1')

    @patch('fitbit_integration.services.requests.post')
    def test_invalid_client_raises_auth_error(self, mock_post):
        make_token(self.user, expires_in_hours=-1)
        mock_post.return_value = FakeResponse(status_code=401, text='invalid_client')

        with self.assertRaises(FitbitAuthError):
            GoogleHealthService(user=self.user).get_valid_access_token()

    @patch('fitbit_integration.services.requests.post')
    def test_invalid_grant_raises_auth_error(self, mock_post):
        # A revoked or expired refresh token comes back as 400
        # invalid_grant. Classifying it as transient would retry a dead
        # grant nightly and never prompt the user to reconnect.
        make_token(self.user, expires_in_hours=-1)
        mock_post.return_value = FakeResponse(
            status_code=400, body={'error': 'invalid_grant'}, text='invalid_grant',
        )

        with self.assertRaises(FitbitAuthError):
            GoogleHealthService(user=self.user).get_valid_access_token()

    @patch('fitbit_integration.services.requests.post')
    def test_refresh_outage_raises_unavailable(self, mock_post):
        make_token(self.user, expires_in_hours=-1)
        mock_post.return_value = FakeResponse(status_code=503, text='down')

        with self.assertRaises(FitbitUnavailable):
            GoogleHealthService(user=self.user).get_valid_access_token()


class ApiRequestErrorTests(TestCase):
    """Errors from the data endpoints get the same classification."""

    def setUp(self):
        self.user = make_user()
        make_token(self.user)
        self.service = GoogleHealthService(user=self.user)

    def list_sleep(self):
        return self.service.list_sleep(date(2026, 9, 1), date(2026, 9, 1))

    @patch('fitbit_integration.services.requests.post')
    @patch('fitbit_integration.services.requests.request')
    def test_persistent_401_raises_auth_error(self, mock_request, mock_post):
        # A 401 triggers one refresh-and-retry; a second 401 means the
        # authorisation itself is gone, not a stale access token.
        mock_request.return_value = FakeResponse(status_code=401, text='expired')
        mock_post.return_value = FakeResponse(body=token_body())

        with self.assertRaises(FitbitAuthError):
            self.list_sleep()

    @patch('fitbit_integration.services.requests.post')
    @patch('fitbit_integration.services.requests.request')
    def test_401_then_success_after_refresh(self, mock_request, mock_post):
        mock_request.side_effect = [
            FakeResponse(status_code=401, text='expired'),
            FakeResponse(body={'dataPoints': [{'name': 'x'}]}),
        ]
        mock_post.return_value = FakeResponse(body=token_body())

        self.assertEqual(self.list_sleep(), [{'name': 'x'}])

    @patch('fitbit_integration.services.requests.request')
    def test_missing_scope_raises_auth_error(self, mock_request):
        mock_request.return_value = FakeResponse(status_code=403, body={'error': {
            'status': 'PERMISSION_DENIED', 'details': [{'reason': 'MISSING_OAUTH_SCOPE'}],
        }})

        with self.assertRaises(FitbitAuthError):
            self.list_sleep()

    @patch('fitbit_integration.services.requests.request')
    def test_server_error_raises_unavailable(self, mock_request):
        mock_request.return_value = FakeResponse(status_code=503, text='down')
        with self.assertRaises(FitbitUnavailable):
            self.list_sleep()

    @patch('fitbit_integration.services.requests.request')
    def test_rate_limit_raises_unavailable(self, mock_request):
        mock_request.return_value = FakeResponse(status_code=429, text='slow down')
        with self.assertRaises(FitbitUnavailable):
            self.list_sleep()

    @patch('fitbit_integration.services.requests.request')
    def test_connection_failure_raises_unavailable(self, mock_request):
        mock_request.side_effect = requests.ConnectionError('no route to host')
        with self.assertRaises(FitbitUnavailable):
            self.list_sleep()

    @patch('fitbit_integration.services.requests.request')
    def test_bad_request_is_not_an_auth_error(self, mock_request):
        # A malformed filter is our bug. It must not disconnect anyone.
        mock_request.return_value = FakeResponse(status_code=400, body={'error': {
            'status': 'INVALID_ARGUMENT', 'details': [{'reason': 'INVALID_DATA_POINT_FILTER'}],
        }})

        with self.assertRaises(FitbitError) as ctx:
            self.list_sleep()
        self.assertNotIsInstance(ctx.exception, FitbitAuthError)


class ListSleepTests(TestCase):

    def setUp(self):
        self.user = make_user()
        make_token(self.user)
        self.service = GoogleHealthService(user=self.user)

    @patch('fitbit_integration.services.requests.request')
    def test_filters_on_local_end_date_inclusive(self, mock_request):
        mock_request.return_value = FakeResponse(body={'dataPoints': []})

        self.service.list_sleep(date(2026, 9, 1), date(2026, 9, 3))

        args, kwargs = mock_request.call_args
        self.assertEqual(
            args[1], 'https://health.googleapis.com/v4/users/me/dataTypes/sleep/dataPoints'
        )
        self.assertEqual(
            kwargs['params']['filter'],
            'sleep.interval.civil_end_time >= "2026-09-01" AND '
            'sleep.interval.civil_end_time < "2026-09-04"',
        )
        self.assertEqual(kwargs['params']['pageSize'], 25)

    @patch('fitbit_integration.services.requests.request')
    def test_follows_page_tokens(self, mock_request):
        mock_request.side_effect = [
            FakeResponse(body={'dataPoints': [{'name': 'a'}], 'nextPageToken': 'p2'}),
            FakeResponse(body={'dataPoints': [{'name': 'b'}]}),
        ]

        points = self.service.list_sleep(date(2026, 9, 1), date(2026, 9, 3))

        self.assertEqual([p['name'] for p in points], ['a', 'b'])
        self.assertEqual(mock_request.call_args_list[1].kwargs['params']['pageToken'], 'p2')


class ParseSleepTests(TestCase):

    def test_classic_log_has_no_stage_minutes(self):
        records = parse_google_health_sleep([{
            'name': 'users/1/dataTypes/sleep/dataPoints/abc',
            'sleep': {
                'interval': {
                    'startTime': '2026-09-01T22:00:00.123456789Z', 'startUtcOffset': '3600s',
                    'endTime': '2026-09-02T06:00:00Z', 'endUtcOffset': '3600s',
                },
                'type': 'CLASSIC',
                'metadata': {'main': False},
                'summary': {'minutesAsleep': '400', 'minutesAwake': '80'},
            },
        }])

        record = records[0]
        self.assertEqual(record['external_id'], 'abc')
        self.assertEqual(record['sleep_type'], 'classic')
        self.assertFalse(record['is_main_sleep'])
        self.assertEqual(record['date_of_sleep'], '2026-09-02')
        self.assertEqual(record['start_time'].hour, 23)
        self.assertEqual(record['duration_minutes'], 479)
        # No minutesInSleepPeriod: efficiency falls back to the interval.
        self.assertEqual(record['efficiency'], 84)
        self.assertNotIn('deep_sleep_minutes', record)

    def test_skips_a_point_without_an_interval(self):
        self.assertEqual(parse_google_health_sleep([{'name': 'x', 'sleep': {}}]), [])
