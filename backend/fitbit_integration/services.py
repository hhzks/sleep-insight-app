"""
Fitbit API Service
"""
import base64
import hashlib
import secrets
import requests
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

from .models import FitbitToken


class FitbitService:
    """Service for interacting with Fitbit API."""
    
    AUTHORIZATION_URL = "https://www.fitbit.com/oauth2/authorize"
    TOKEN_URL = "https://api.fitbit.com/oauth2/token"
    API_BASE_URL = "https://api.fitbit.com"
    
    def __init__(self, user=None):
        self.user = user
        self.client_id = settings.FITBIT_CLIENT_ID
        self.client_secret = settings.FITBIT_CLIENT_SECRET
        self.redirect_uri = settings.FITBIT_REDIRECT_URI
        print(self.user, self.client_id, self.client_secret, self.redirect_uri)
    
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
        """Build the authorization URL."""
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'code_challenge': code_challenge,
            'code_challenge_method': 'S256',
            'redirect_uri': self.redirect_uri,
            'scope': 'sleep',
        }
        if state:
            params['state'] = state
        
        from urllib.parse import urlencode
        return f"{self.AUTHORIZATION_URL}?{urlencode(params)}"
    
    def exchange_code_for_tokens(self, auth_code, code_verifier):
        """Exchange authorization code for access tokens."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'client_id': self.client_id,
            'grant_type': 'authorization_code',
            'code': auth_code,
            'code_verifier': code_verifier,
            'redirect_uri': self.redirect_uri,
        }
        
        response = requests.post(self.TOKEN_URL, headers=headers, data=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")
    
    def refresh_access_token(self, refresh_token):
        """Refresh the access token."""
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
        }
        
        response = requests.post(self.TOKEN_URL, headers=headers, data=data)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Token refresh failed: {response.status_code} - {response.text}")
    
    def save_tokens(self, token_data):
        """Save tokens for the user."""
        if not self.user:
            raise ValueError("User is required to save tokens")
        
        expires_at = timezone.now() + timedelta(seconds=token_data.get('expires_in', 28800))
        
        token, created = FitbitToken.objects.update_or_create(
            user=self.user,
            defaults={
                'access_token': token_data['access_token'],
                'refresh_token': token_data['refresh_token'],
                'token_type': token_data.get('token_type', 'Bearer'),
                'expires_at': expires_at,
                'scope': token_data.get('scope', 'sleep'),
                'fitbit_user_id': token_data.get('user_id', ''),
            }
        )
        
        return token
    
    def get_valid_access_token(self):
        """Get a valid access token, refreshing if necessary."""
        if not self.user:
            raise ValueError("User is required")
        
        try:
            token = FitbitToken.objects.get(user=self.user)
        except FitbitToken.DoesNotExist:
            raise Exception("User has not connected Fitbit")
        
        if token.is_expired:
            # Refresh the token
            token_data = self.refresh_access_token(token.refresh_token)
            token = self.save_tokens(token_data)
        
        return token.access_token
    
    def _make_api_request(self, endpoint, method='GET', **kwargs):
        """Make an authenticated API request."""
        access_token = self.get_valid_access_token()
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json',
            **kwargs.pop('headers', {})
        }
        
        url = f"{self.API_BASE_URL}{endpoint}"
        
        response = requests.request(method, url, headers=headers, **kwargs)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Token might be invalid, try refreshing
            token = FitbitToken.objects.get(user=self.user)
            token_data = self.refresh_access_token(token.refresh_token)
            self.save_tokens(token_data)
            
            # Retry request
            headers['Authorization'] = f'Bearer {token_data["access_token"]}'
            response = requests.request(method, url, headers=headers, **kwargs)
            
            if response.status_code == 200:
                return response.json()
        
        raise Exception(f"API request failed: {response.status_code} - {response.text}")
    
    def get_sleep_log_by_date(self, date):
        """Get sleep log for a specific date."""
        endpoint = f"/1.2/user/-/sleep/date/{date}.json"
        return self._make_api_request(endpoint)
    
    def get_sleep_log_range(self, start_date, end_date):
        """Get sleep logs for a date range."""
        endpoint = f"/1.2/user/-/sleep/date/{start_date}/{end_date}.json"
        return self._make_api_request(endpoint)
    
    def get_sleep_log_list(self, before_date=None, limit=100):
        """Get a list of sleep logs."""
        if not before_date:
            before_date = datetime.now().strftime('%Y-%m-%d')
        
        endpoint = f"/1.2/user/-/sleep/list.json?beforeDate={before_date}&sort=desc&offset=0&limit={limit}"
        return self._make_api_request(endpoint)


def parse_fitbit_sleep_data(sleep_data):
    """Parse Fitbit sleep API response into normalized format."""
    records = []
    
    for sleep in sleep_data.get('sleep', []):
        record = {
            'external_id': str(sleep.get('logId', '')),
            'date_of_sleep': sleep.get('dateOfSleep'),
            'start_time': sleep.get('startTime'),
            'end_time': sleep.get('endTime'),
            'duration_minutes': sleep.get('duration', 0) // 60000,  # Convert ms to minutes
            'minutes_asleep': sleep.get('minutesAsleep', 0),
            'minutes_awake': sleep.get('minutesAwake', 0),
            'efficiency': sleep.get('efficiency', 0),
            'is_main_sleep': sleep.get('isMainSleep', False),
            'sleep_type': sleep.get('type', 'classic'),
            'source': 'fitbit',
        }
        
        # Extract sleep stages if available
        levels = sleep.get('levels', {})
        summary = levels.get('summary', {})
        
        if summary:
            record['deep_sleep_minutes'] = summary.get('deep', {}).get('minutes')
            record['light_sleep_minutes'] = summary.get('light', {}).get('minutes')
            record['rem_sleep_minutes'] = summary.get('rem', {}).get('minutes')
        
        # Extract detailed stage data
        stage_data = []
        for stage_entry in levels.get('data', []):
            stage_data.append({
                'stage': stage_entry.get('level'),
                'start_time': stage_entry.get('dateTime'),
                'duration_seconds': stage_entry.get('seconds', 0),
            })
        
        record['stage_data'] = stage_data
        records.append(record)
    
    return records
