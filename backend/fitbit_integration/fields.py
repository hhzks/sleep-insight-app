"""Encryption at rest for Fitbit OAuth tokens.

These are long-lived Fitbit grants, and since the nightly sync refreshes
and uses them with no user present, their usefulness to anyone reading the
database is not bounded by a session. They are stored as Fernet ciphertext
and decrypted only on the way into FitbitService.

Keys come from FITBIT_TOKEN_ENCRYPTION_KEYS, newest first. MultiFernet
decrypts with any key in the list and encrypts with the first, so rotating
is: mint a key, prepend it, re-save the rows, drop the old key.
"""
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


@lru_cache(maxsize=1)
def build_cipher():
    """Assemble the MultiFernet from configured keys.

    Deliberately lazy rather than built at import: management commands that
    never touch a token (collectstatic, makemigrations) must not require the
    key to be present. Cached because Fernet key derivation is not free and
    this runs on every token read.
    """
    keys = getattr(settings, 'FITBIT_TOKEN_ENCRYPTION_KEYS', [])

    if not keys:
        raise ImproperlyConfigured(
            'FITBIT_TOKEN_ENCRYPTION_KEYS is not set, so Fitbit tokens cannot '
            'be encrypted or read. Generate one with: python -c "from '
            'cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

    try:
        return MultiFernet([Fernet(key) for key in keys])
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured(
            f'FITBIT_TOKEN_ENCRYPTION_KEYS contains an invalid Fernet key: {exc}'
        ) from exc


def encrypt(value):
    """Encrypt a token for storage. Returns str."""
    return build_cipher().encrypt(value.encode()).decode()


def decrypt(value):
    """Decrypt a stored token. Returns str."""
    try:
        return build_cipher().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        # Either the writing key is no longer in the list, or the column
        # holds something that was never encrypted. Both need a human.
        raise ImproperlyConfigured(
            'A stored Fitbit token could not be decrypted with any key in '
            'FITBIT_TOKEN_ENCRYPTION_KEYS. If a key was retired, restore it '
            'to the list and re-save the rows before removing it again.'
        ) from exc


def looks_encrypted(value):
    """Whether a stored value decrypts with a configured key.

    Used by the migration to stay idempotent: a retried release_command must
    not encrypt an already-encrypted column a second time.
    """
    if not value:
        return False

    try:
        build_cipher().decrypt(value.encode())
    except InvalidToken:
        return False

    return True


TOKEN_COLUMNS = ('access_token', 'refresh_token')


def _convert_token_columns(connection, convert):
    """Rewrite both token columns of every row through `convert`.

    Raw SQL on both sides on purpose: once the model declares
    EncryptedTextField, an ORM read would try to decrypt values that are
    still plaintext, and an ORM write would encrypt values that are already
    ciphertext. The migration has to see the columns exactly as stored.
    """
    columns = ', '.join(TOKEN_COLUMNS)
    assignments = ', '.join(f'{column} = %s' for column in TOKEN_COLUMNS)

    with connection.cursor() as cursor:
        cursor.execute(f'SELECT id, {columns} FROM fitbit_tokens')
        rows = cursor.fetchall()

        for row_id, *values in rows:
            converted = [convert(value) for value in values]

            if converted == values:
                continue

            cursor.execute(
                f'UPDATE fitbit_tokens SET {assignments} WHERE id = %s',
                [*converted, row_id],
            )


def encrypt_token_columns(connection):
    """Encrypt any plaintext token columns in place.

    Idempotent: already-encrypted values are left alone, so a retried
    release_command cannot double-encrypt them.
    """
    _convert_token_columns(
        connection,
        lambda value: value if looks_encrypted(value) else encrypt(value),
    )


def decrypt_token_columns(connection):
    """Restore plaintext token columns. The reverse of the 0003 migration."""
    _convert_token_columns(
        connection,
        lambda value: decrypt(value) if looks_encrypted(value) else value,
    )


class EncryptedTextField(models.TextField):
    """A TextField whose value is Fernet-encrypted in the database.

    Callers see plaintext in both directions, which is what lets
    services.py stay unaware that any of this happens. The column stays
    TEXT, so this is a no-op at the schema level - only the contents change.

    Values cannot be filtered or ordered on: every row has a distinct
    ciphertext for the same plaintext. Nothing queries tokens by value.
    """

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return decrypt(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None:
            return value
        return encrypt(value)
