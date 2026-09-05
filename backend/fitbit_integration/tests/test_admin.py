"""
The admin must not undo encryption at rest by rendering the tokens.
"""
from django.contrib.admin.sites import site
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from fitbit_integration.models import FitbitToken

User = get_user_model()


class FitbitTokenAdminTests(TestCase):
    def setUp(self):
        self.model_admin = site._registry[FitbitToken]
        self.request = RequestFactory().get('/admin/')
        self.request.user = User.objects.create(
            email='staff@example.com', firebase_uid='uid-staff',
            is_staff=True, is_superuser=True,
        )

    def test_token_values_are_not_on_the_change_form(self):
        fields = self.model_admin.get_fields(self.request)

        self.assertNotIn('access_token', fields)
        self.assertNotIn('refresh_token', fields)

    def test_token_values_are_not_displayed_as_readonly(self):
        # readonly_fields still renders the value on the change page, and the
        # field decrypts on read - so listing them there hands the plaintext
        # to every staff user, which is what encrypting at rest is for.
        self.assertNotIn('access_token', self.model_admin.readonly_fields)
        self.assertNotIn('refresh_token', self.model_admin.readonly_fields)

    def test_token_values_are_not_in_the_list_view(self):
        self.assertNotIn('access_token', self.model_admin.list_display)
        self.assertNotIn('refresh_token', self.model_admin.list_display)

    def test_expiry_is_still_visible(self):
        # The page has to stay useful for support: who is connected and
        # whether their grant is current.
        self.assertIn('expires_at', self.model_admin.list_display)
