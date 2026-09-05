"""Encrypt the Fitbit token columns in place.

Both AlterField operations are schema no-ops - EncryptedTextField is still
TEXT - so the real work is the data conversion, which rewrites existing
plaintext as Fernet ciphertext.

This runs in release_command, before any new machine takes traffic. With
FITBIT_TOKEN_ENCRYPTION_KEYS unset it raises ImproperlyConfigured, the
release command exits non-zero, and Fly aborts the deploy with the old code
still serving. Set the secret before deploying this.
"""
from django.db import migrations

import fitbit_integration.fields
from fitbit_integration.fields import decrypt_token_columns, encrypt_token_columns


def encrypt_existing_tokens(apps, schema_editor):
    encrypt_token_columns(schema_editor.connection)


def decrypt_existing_tokens(apps, schema_editor):
    decrypt_token_columns(schema_editor.connection)


class Migration(migrations.Migration):

    dependencies = [
        ('fitbit_integration', '0002_fitbittoken_auto_sync_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fitbittoken',
            name='access_token',
            field=fitbit_integration.fields.EncryptedTextField(),
        ),
        migrations.AlterField(
            model_name='fitbittoken',
            name='refresh_token',
            field=fitbit_integration.fields.EncryptedTextField(),
        ),
        migrations.RunPython(encrypt_existing_tokens, decrypt_existing_tokens),
    ]
