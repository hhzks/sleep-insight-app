"""
Tests for the Fitbit API service's error classification.

The scheduled sync has to tell "this user's authorisation is dead" apart
from "Fitbit had a bad minute": the first counts towards disconnecting
them, the second must never touch that counter.
"""
from datetime import timedelta
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from fitbit_integration.models import FitbitToken
from fitbit_integration.services import (
    FitbitAuthError,
    FitbitService,
    FitbitUnavailable,
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


def make_token(user, expires_in_hours=8):
    return FitbitToken.objects.create(
        user=user,
        access_token='access-1',
        refresh_token='refresh-1',
        expires_at=timezone.now() + timedelta(hours=expires_in_hours),
    )


class TokenRefreshErrorTests(TestCase):
    """A rejected refresh means the user must reconnect."""

    def setUp(self):
        self.user = make_user()

    def test_missing_token_raises_auth_error(self):
        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitAuthError):
            service.get_valid_access_token()

    @patch('fitbit_integration.services.requests.post')
    def test_rejected_refresh_raises_auth_error(self, mock_post):
        make_token(self.user, expires_in_hours=-1)
        mock_post.return_value = FakeResponse(status_code=401, text='invalid_grant')

        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitAuthError):
            service.get_valid_access_token()

    @patch('fitbit_integration.services.requests.post')
    def test_invalid_grant_raises_auth_error(self, mock_post):
        # Revoking access in Fitbit's own settings retires the refresh
        # token, and Fitbit reports that as 400 invalid_grant rather than
        # 401. Classifying it as transient would retry a dead grant nightly
        # and never prompt the user to reconnect.
        make_token(self.user, expires_in_hours=-1)
        mock_post.return_value = FakeResponse(
            status_code=400,
            body={'errors': [{'errorType': 'invalid_grant'}]},
            text='invalid_grant',
        )

        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitAuthError):
            service.get_valid_access_token()

    @patch('fitbit_integration.services.requests.post')
    def test_refresh_outage_raises_unavailable(self, mock_post):
        make_token(self.user, expires_in_hours=-1)
        mock_post.return_value = FakeResponse(status_code=503, text='down')

        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitUnavailable):
            service.get_valid_access_token()


class ApiRequestErrorTests(TestCase):
    """Errors from the data endpoints get the same classification."""

    def setUp(self):
        self.user = make_user()
        make_token(self.user)

    @patch('fitbit_integration.services.requests.post')
    @patch('fitbit_integration.services.requests.request')
    def test_persistent_401_raises_auth_error(self, mock_request, mock_post):
        # A 401 triggers one refresh-and-retry; a second 401 means the
        # authorisation itself is gone, not a stale access token.
        mock_request.return_value = FakeResponse(status_code=401, text='expired')
        mock_post.return_value = FakeResponse(
            body={'access_token': 'a2', 'refresh_token': 'r2', 'expires_in': 28800}
        )

        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitAuthError):
            service.get_sleep_log_by_date('2026-09-01')

    @patch('fitbit_integration.services.requests.request')
    def test_server_error_raises_unavailable(self, mock_request):
        mock_request.return_value = FakeResponse(status_code=503, text='down')

        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitUnavailable):
            service.get_sleep_log_by_date('2026-09-01')

    @patch('fitbit_integration.services.requests.request')
    def test_rate_limit_raises_unavailable(self, mock_request):
        mock_request.return_value = FakeResponse(status_code=429, text='slow down')

        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitUnavailable):
            service.get_sleep_log_by_date('2026-09-01')

    @patch('fitbit_integration.services.requests.request')
    def test_connection_failure_raises_unavailable(self, mock_request):
        mock_request.side_effect = requests.ConnectionError('no route to host')

        service = FitbitService(user=self.user)
        with self.assertRaises(FitbitUnavailable):
            service.get_sleep_log_by_date('2026-09-01')
