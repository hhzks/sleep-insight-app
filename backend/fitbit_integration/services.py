"""
Google Health API service.

Google turned off the legacy Fitbit Web API on 2 November 2026. Fitbit
devices now report through the Google Health API, which uses Google OAuth
and a different response schema. The rest of this app still calls the
feature "Fitbit" because the data still comes from Fitbit devices.

Docs: https://developers.google.com/health
"""
import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone
from urllib.parse import urlencode

import requests
from django.conf import settings
from django.utils import timezone

from .models import FitbitToken

logger = logging.getLogger(__name__)

SLEEP_READ_SCOPE = 'https://www.googleapis.com/auth/googlehealth.sleep.readonly'

# The list method caps sleep pages at 25 data points. 60 pages is 1,500
# nights, which covers the 365-day maximum sync window with a wide margin
# and stops a pagination fault from looping forever.
SLEEP_PAGE_SIZE = 25
MAX_SLEEP_PAGES = 60

REQUEST_TIMEOUT_SECONDS = 30


class FitbitError(Exception):
    """Base class for every failure talking to Google Health."""


class FitbitAuthError(FitbitError):
    """The user's authorisation is gone; only reconnecting fixes it.

    Raised for a rejected refresh token, for a 401 that survives the
    refresh-and-retry, for a missing scope, and for a Google account with
    no Google Health profile. The scheduled sync counts these towards
    disconnecting the user, so nothing transient may raise this.
    """


class FitbitUnavailable(FitbitError):
    """Google Health could not be reached or would not answer right now.

    Network failures, 5xx, and 429. Retrying later is the right response;
    the user's authorisation is not in question.
    """


def _error_reason(response):
    """Return the Google error reason (e.g. 'ACCOUNT_NOT_LINKED'), or ''."""
    try:
        error = response.json().get('error', {})
    except (ValueError, AttributeError):
        return ''
    if not isinstance(error, dict):
        return ''
    for detail in error.get('details', []) or []:
        if isinstance(detail, dict) and detail.get('reason'):
            return detail['reason']
    return error.get('status', '') or ''


class GoogleHealthService:
    """Client for the Google Health API (sleep only)."""

    AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    API_BASE_URL = "https://health.googleapis.com/v4"

    def __init__(self, user=None):
        self.user = user
        self.client_id = settings.GOOGLE_HEALTH_CLIENT_ID
        self.client_secret = settings.GOOGLE_HEALTH_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_HEALTH_REDIRECT_URI

    # ------------------------------------------------------------------ OAuth

    @staticmethod
    def generate_code_verifier():
        """Generate a code verifier for PKCE."""
        return secrets.token_urlsafe(64)[:128]

    @staticmethod
    def generate_code_challenge(verifier):
        """Generate a code challenge from the verifier."""
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b'=').decode()

    def get_authorization_url(self, code_challenge, state=None):
        """Build the Google consent URL."""
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'response_type': 'code',
            'scope': SLEEP_READ_SCOPE,
            # The nightly sync runs with no user present, so it needs a
            # refresh token. Google only issues one with offline access,
            # and only re-issues it on an explicit consent prompt.
            'access_type': 'offline',
            'prompt': 'consent',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
        }
        if state:
            params['state'] = state
        return f"{self.AUTHORIZATION_URL}?{urlencode(params)}"

    def exchange_code_for_tokens(self, auth_code, code_verifier):
        """Exchange an authorization code for access and refresh tokens."""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'authorization_code',
            'code': auth_code,
            'code_verifier': code_verifier,
            'redirect_uri': self.redirect_uri,
        }
        response = self._post_token(data)

        if response.status_code == 200:
            return response.json()

        raise FitbitError(
            f"Token exchange failed: {response.status_code} - {response.text}"
        )

    def refresh_access_token(self, refresh_token):
        """Get a new access token from a refresh token."""
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }
        response = self._post_token(data)

        if response.status_code == 200:
            return response.json()

        # Google answers a revoked or expired refresh token with 400
        # invalid_grant, and a bad client credential with 401
        # invalid_client. Both mean reconnecting is the only way forward;
        # anything else is Google's problem, not the user's.
        if response.status_code in (400, 401):
            raise FitbitAuthError(
                f"Token refresh rejected: {response.status_code} - {response.text}"
            )

        raise FitbitUnavailable(
            f"Token refresh failed: {response.status_code} - {response.text}"
        )

    def _post_token(self, data):
        try:
            return requests.post(
                self.TOKEN_URL,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                data=data,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise FitbitUnavailable(f"Could not reach Google OAuth: {exc}") from exc

    def connect(self, auth_code, code_verifier):
        """Finish the OAuth flow: exchange the code, check it, save tokens.

        Returns the saved FitbitToken. Nothing is saved unless the grant
        can read sleep and the Google account has a Google Health profile,
        so the UI never shows "connected" for a link that cannot sync.
        """
        if not self.user:
            raise ValueError("User is required to connect")

        token_data = self.exchange_code_for_tokens(auth_code, code_verifier)

        granted = (token_data.get('scope') or '').split()
        if granted and SLEEP_READ_SCOPE not in granted:
            raise FitbitAuthError(
                'Sleep access was not granted. Connect again and allow '
                'access to your sleep data.'
            )
        if not token_data.get('refresh_token'):
            raise FitbitError(
                'Google did not issue a refresh token. Remove this app from '
                'your Google account permissions, then connect again.'
            )

        identity = self._get_identity(token_data['access_token'])
        token_data['user_id'] = identity.get('healthUserId', '')

        return self.save_tokens(token_data)

    def _get_identity(self, access_token):
        """Read the Google Health user id for a fresh access token."""
        response = self._send(
            'GET',
            f"{self.API_BASE_URL}/users/me/identity",
            headers={
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json',
            },
        )
        if response.status_code == 200:
            return response.json()
        self._raise_for_response(response)

    def save_tokens(self, token_data):
        """Save tokens for the user.

        A refresh response from Google does not always include a refresh
        token. When it is missing, the stored one stays valid and is kept.
        """
        if not self.user:
            raise ValueError("User is required to save tokens")

        expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 3600))

        defaults = {
            'access_token': token_data['access_token'],
            'token_type': token_data.get('token_type', 'Bearer'),
            'expires_at': expires_at,
        }
        if token_data.get('refresh_token'):
            defaults['refresh_token'] = token_data['refresh_token']
        if token_data.get('scope'):
            defaults['scope'] = token_data['scope']
        if token_data.get('user_id'):
            defaults['fitbit_user_id'] = token_data['user_id']

        token, _ = FitbitToken.objects.update_or_create(user=self.user, defaults=defaults)
        return token

    def get_valid_access_token(self):
        """Get a valid access token, refreshing if necessary."""
        if not self.user:
            raise ValueError("User is required")

        try:
            token = FitbitToken.objects.get(user=self.user)
        except FitbitToken.DoesNotExist:
            raise FitbitAuthError("User has not connected Fitbit")

        if token.is_expired:
            token_data = self.refresh_access_token(token.refresh_token)
            token = self.save_tokens(token_data)

        return token.access_token

    # -------------------------------------------------------------- Requests

    def _make_api_request(self, path, params=None):
        """Make an authenticated GET request and return the JSON body."""
        access_token = self.get_valid_access_token()
        url = f"{self.API_BASE_URL}{path}"
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
        }

        response = self._send('GET', url, headers=headers, params=params)

        if response.status_code == 401:
            # The access token may merely be stale. Refresh once and retry;
            # a second 401 means the authorisation itself is gone.
            token = FitbitToken.objects.get(user=self.user)
            token_data = self.refresh_access_token(token.refresh_token)
            self.save_tokens(token_data)

            headers['Authorization'] = f'Bearer {token_data["access_token"]}'
            response = self._send('GET', url, headers=headers, params=params)

        if response.status_code == 200:
            return response.json()

        self._raise_for_response(response)

    @staticmethod
    def _raise_for_response(response):
        """Map a failed Google Health response to the right FitbitError."""
        status = response.status_code
        reason = _error_reason(response)
        detail = f"{status} {reason} - {response.text}".strip()

        if status == 401:
            raise FitbitAuthError(f"Authorisation rejected after refresh: {detail}")
        if status == 403:
            # MISSING_OAUTH_SCOPE, or a legacy Fitbit login that Google
            # cannot map to a Google Health profile. Both need a reconnect.
            raise FitbitAuthError(f"Google Health refused access: {detail}")
        if reason == 'ACCOUNT_NOT_LINKED':
            raise FitbitAuthError(
                'This Google account has no Google Health profile. Link your '
                'Fitbit account to Google at https://fitbit.google.com, then '
                'connect again.'
            )
        if status == 429 or status >= 500:
            raise FitbitUnavailable(f"API request failed: {detail}")
        raise FitbitError(f"API request failed: {detail}")

    def _send(self, method, url, **kwargs):
        """Issue one HTTP request, mapping transport failures to FitbitUnavailable."""
        kwargs.setdefault('timeout', REQUEST_TIMEOUT_SECONDS)
        try:
            return requests.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise FitbitUnavailable(f"Could not reach Google Health: {exc}") from exc

    # ------------------------------------------------------------------ Sleep

    def list_sleep(self, start_date, end_date):
        """Return every sleep data point that ends on a local date in the range.

        Both dates are inclusive and are compared with the civil (local)
        end time, which matches how Fitbit's dateOfSleep was assigned.
        """
        end_exclusive = end_date + timedelta(days=1)
        params = {
            'filter': (
                f'sleep.interval.civil_end_time >= "{start_date.isoformat()}" AND '
                f'sleep.interval.civil_end_time < "{end_exclusive.isoformat()}"'
            ),
            'pageSize': SLEEP_PAGE_SIZE,
        }

        data_points = []
        for _ in range(MAX_SLEEP_PAGES):
            body = self._make_api_request('/users/me/dataTypes/sleep/dataPoints', params=params)
            data_points.extend(body.get('dataPoints', []))

            next_token = body.get('nextPageToken')
            if not next_token:
                return data_points
            params = {**params, 'pageToken': next_token}

        logger.warning(
            'Stopped sleep pagination for user %s after %s pages',
            getattr(self.user, 'pk', None), MAX_SLEEP_PAGES,
        )
        return data_points


# ---------------------------------------------------------------------- Parsing

STAGE_MAP = {
    'AWAKE': 'wake',
    'LIGHT': 'light',
    'DEEP': 'deep',
    'REM': 'rem',
    # Classic (non-staged) logs.
    'ASLEEP': 'asleep',
    'RESTLESS': 'restless',
}


def _parse_instant(value):
    """Parse an RFC 3339 timestamp into an aware UTC datetime."""
    if value.endswith('Z'):
        value = value[:-1] + '+00:00'
    # Python before 3.11 rejects more than 6 fractional digits.
    if '.' in value:
        head, _, tail = value.partition('.')
        digits = ''.join(ch for ch in tail if ch.isdigit())
        zone = tail[len(digits):]
        value = f"{head}.{digits[:6]}{zone}"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed.astimezone(dt_timezone.utc)


def _parse_offset(value):
    """Parse a Google duration offset such as '-14400s' into a timedelta."""
    if not value:
        return timedelta(0)
    return timedelta(seconds=float(str(value).rstrip('s')))


def _wall_clock(instant, offset):
    """Return the local wall-clock time, labelled as UTC.

    The Fitbit Web API returned local times with no zone, and Django stored
    them as UTC. Existing records and every chart rely on that, so new
    records keep the same convention.
    """
    return (_parse_instant(instant) + _parse_offset(offset)).replace(tzinfo=dt_timezone.utc)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def parse_google_health_sleep(data_points):
    """Convert Google Health sleep data points into normalized records."""
    records = []

    for point in data_points:
        sleep = point.get('sleep') or {}
        interval = sleep.get('interval') or {}
        if not interval.get('startTime') or not interval.get('endTime'):
            continue

        start = _wall_clock(interval['startTime'], interval.get('startUtcOffset'))
        end = _wall_clock(interval['endTime'], interval.get('endUtcOffset'))
        duration_minutes = max(0, int((end - start).total_seconds() // 60))

        summary = sleep.get('summary') or {}
        metadata = sleep.get('metadata') or {}
        minutes_asleep = _int(summary.get('minutesAsleep'))
        minutes_in_period = _int(summary.get('minutesInSleepPeriod')) or duration_minutes

        efficiency = 0
        if minutes_in_period:
            efficiency = min(100, round(minutes_asleep / minutes_in_period * 100))

        sleep_type = 'stages' if str(sleep.get('type', '')).upper() == 'STAGES' else 'classic'

        record = {
            'external_id': point.get('name', '').rsplit('/', 1)[-1],
            'date_of_sleep': end.date().isoformat(),
            'start_time': start,
            'end_time': end,
            'duration_minutes': duration_minutes,
            'minutes_asleep': minutes_asleep,
            'minutes_awake': _int(summary.get('minutesAwake')),
            'efficiency': efficiency,
            'is_main_sleep': bool(metadata.get('main', False)),
            'sleep_type': sleep_type,
            'source': 'fitbit',
        }

        stage_data = []
        for stage in sleep.get('stages') or []:
            mapped = STAGE_MAP.get(str(stage.get('type', '')).upper())
            if not mapped or not stage.get('startTime') or not stage.get('endTime'):
                continue
            stage_start = _wall_clock(stage['startTime'], stage.get('startUtcOffset'))
            stage_end = _wall_clock(stage['endTime'], stage.get('endUtcOffset'))
            stage_data.append({
                'stage': mapped,
                'start_time': stage_start,
                'duration_seconds': max(0, int((stage_end - stage_start).total_seconds())),
            })

        if sleep_type == 'stages':
            minutes = {}
            for entry in summary.get('stagesSummary') or sleep.get('stagesSummary') or []:
                mapped = STAGE_MAP.get(str(entry.get('type', '')).upper())
                if mapped:
                    minutes[mapped] = _int(entry.get('minutes'))
            if not minutes:
                for stage in stage_data:
                    minutes[stage['stage']] = minutes.get(stage['stage'], 0) + stage['duration_seconds'] // 60
            record['deep_sleep_minutes'] = minutes.get('deep')
            record['light_sleep_minutes'] = minutes.get('light')
            record['rem_sleep_minutes'] = minutes.get('rem')

        record['stage_data'] = stage_data
        records.append(record)

    return records
