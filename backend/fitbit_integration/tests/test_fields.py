"""
Tests for encryption of Fitbit OAuth tokens at rest.

The tokens are long-lived Fitbit grants that the nightly sync uses with no
user present, so anyone reading the database must not read the tokens.
"""
from datetime import timedelta

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import TestCase, override_settings
from django.utils import timezone

from fitbit_integration.fields import (
    build_cipher,
    decrypt,
    decrypt_token_columns,
    encrypt,
    encrypt_token_columns,
)
from fitbit_integration.models import FitbitToken

User = get_user_model()

KEY_A = Fernet.generate_key().decode()
KEY_B = Fernet.generate_key().decode()

ACCESS = 'fitbit-access-token-value'
REFRESH = 'fitbit-refresh-token-value'


def stored_columns(token_pk):
    """Read the raw columns, bypassing the field's decryption."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT access_token, refresh_token FROM fitbit_tokens WHERE id = %s',
            [token_pk],
        )
        return cursor.fetchone()


@override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=[KEY_A])
class EncryptedTokenStorageTests(TestCase):
    def setUp(self):
        build_cipher.cache_clear()
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')

    def tearDown(self):
        build_cipher.cache_clear()

    def make_token(self):
        return FitbitToken.objects.create(
            user=self.user,
            access_token=ACCESS,
            refresh_token=REFRESH,
            expires_at=timezone.now() + timedelta(hours=8),
        )

    def test_tokens_read_back_as_plaintext(self):
        # Call sites in services.py are unchanged, so the field has to hide
        # the encryption completely on the way out.
        token = self.make_token()
        reloaded = FitbitToken.objects.get(pk=token.pk)

        self.assertEqual(reloaded.access_token, ACCESS)
        self.assertEqual(reloaded.refresh_token, REFRESH)

    def test_columns_hold_ciphertext_not_plaintext(self):
        token = self.make_token()

        access_column, refresh_column = stored_columns(token.pk)

        self.assertNotIn(ACCESS, access_column)
        self.assertNotIn(REFRESH, refresh_column)

    def test_stored_ciphertext_decrypts_with_the_configured_key(self):
        token = self.make_token()
        access_column, _ = stored_columns(token.pk)

        plaintext = Fernet(KEY_A).decrypt(access_column.encode()).decode()

        self.assertEqual(plaintext, ACCESS)

    def test_updating_a_token_re_encrypts_it(self):
        token = self.make_token()
        token.access_token = 'rotated-access-token'
        token.save()

        access_column, _ = stored_columns(token.pk)

        self.assertNotIn('rotated-access-token', access_column)
        self.assertEqual(FitbitToken.objects.get(pk=token.pk).access_token, 'rotated-access-token')


class KeyRotationTests(TestCase):
    """MultiFernet decrypts with any key and encrypts with the first."""

    def setUp(self):
        build_cipher.cache_clear()

    def tearDown(self):
        build_cipher.cache_clear()

    def test_a_value_written_under_an_old_key_still_decrypts(self):
        with override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=[KEY_B]):
            build_cipher.cache_clear()
            ciphertext = encrypt(ACCESS)

        # KEY_B has been demoted behind a newly minted KEY_A.
        with override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=[KEY_A, KEY_B]):
            build_cipher.cache_clear()
            self.assertEqual(decrypt(ciphertext), ACCESS)

    def test_new_values_are_written_under_the_first_key(self):
        with override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=[KEY_A, KEY_B]):
            build_cipher.cache_clear()
            ciphertext = encrypt(ACCESS)

        # Decrypting with KEY_A alone proves the newest key was used, which
        # is what makes rotation actually retire the old one.
        self.assertEqual(Fernet(KEY_A).decrypt(ciphertext.encode()).decode(), ACCESS)


class MissingKeyTests(TestCase):
    """An unset key must stop the app, not silently store plaintext."""

    def setUp(self):
        build_cipher.cache_clear()

    def tearDown(self):
        build_cipher.cache_clear()

    @override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=[])
    def test_encrypting_without_a_key_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            encrypt(ACCESS)

    @override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=[])
    def test_decrypting_without_a_key_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            decrypt('gAAAAABanything')

    @override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=['not-a-valid-fernet-key'])
    def test_a_malformed_key_raises(self):
        with self.assertRaises(ImproperlyConfigured):
            encrypt(ACCESS)


@override_settings(FITBIT_TOKEN_ENCRYPTION_KEYS=[KEY_A])
class BulkEncryptionTests(TestCase):
    """The conversion the 0003 migration performs on existing rows."""

    def setUp(self):
        build_cipher.cache_clear()
        self.user = User.objects.create(email='sleeper@example.com', firebase_uid='uid-1')
        self.token = FitbitToken.objects.create(
            user=self.user,
            access_token=ACCESS,
            refresh_token=REFRESH,
            expires_at=timezone.now() + timedelta(hours=8),
        )

    def tearDown(self):
        build_cipher.cache_clear()

    def write_plaintext(self):
        """Put the row back the way it looked before this feature."""
        with connection.cursor() as cursor:
            cursor.execute(
                'UPDATE fitbit_tokens SET access_token = %s, refresh_token = %s WHERE id = %s',
                [ACCESS, REFRESH, self.token.pk],
            )

    def test_plaintext_rows_become_ciphertext(self):
        self.write_plaintext()

        encrypt_token_columns(connection)

        access_column, refresh_column = stored_columns(self.token.pk)
        self.assertNotIn(ACCESS, access_column)
        self.assertNotIn(REFRESH, refresh_column)

    def test_converted_rows_read_back_through_the_orm(self):
        self.write_plaintext()

        encrypt_token_columns(connection)

        reloaded = FitbitToken.objects.get(pk=self.token.pk)
        self.assertEqual(reloaded.access_token, ACCESS)
        self.assertEqual(reloaded.refresh_token, REFRESH)

    def test_running_twice_does_not_double_encrypt(self):
        # release_command is retried after a failed deploy, so a second run
        # over already-converted rows has to be a no-op.
        self.write_plaintext()

        encrypt_token_columns(connection)
        encrypt_token_columns(connection)

        self.assertEqual(FitbitToken.objects.get(pk=self.token.pk).access_token, ACCESS)

    def test_reverse_restores_plaintext(self):
        # The migration is reversible so a rollback does not strand the data.
        decrypt_token_columns(connection)

        access_column, refresh_column = stored_columns(self.token.pk)
        self.assertEqual(access_column, ACCESS)
        self.assertEqual(refresh_column, REFRESH)

    def test_reverse_then_forward_round_trips(self):
        decrypt_token_columns(connection)
        encrypt_token_columns(connection)

        self.assertEqual(FitbitToken.objects.get(pk=self.token.pk).access_token, ACCESS)
