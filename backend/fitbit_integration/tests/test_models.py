"""
Tests for the FitbitToken fields the scheduled sync depends on.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from fitbit_integration.models import FitbitToken

User = get_user_model()


class FitbitTokenDefaultsTests(TestCase):
    """Connecting Fitbit opts a user into nightly sync."""

    def setUp(self):
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    def make_token(self):
        return FitbitToken.objects.create(
            user=self.user,
            access_token='access-1',
            refresh_token='refresh-1',
            expires_at=timezone.now() + timedelta(hours=8),
        )

    def test_auto_sync_defaults_to_on(self):
        # Users who connected before this feature existed must be swept up
        # by the nightly run without any migration backfill.
        self.assertTrue(self.make_token().auto_sync)

    def test_auth_failures_start_at_zero(self):
        self.assertEqual(self.make_token().consecutive_auth_failures, 0)
