"""Move Fitbit connections to the Google Health API.

Google turned off the legacy Fitbit Web API and its OAuth endpoints on
2 November 2026. Fitbit access and refresh tokens cannot be transferred to
Google OAuth, so every stored grant is dead. Deleting the rows is exactly
what manual disconnection does: the UI shows "not connected" and each user
connects again through Google. Imported sleep records are kept; the next
sync re-keys them to Google Health ids (see sync._adopt_legacy_record).

The reverse step cannot bring back the deleted grants and does nothing.
"""
from django.db import migrations, models


def delete_legacy_tokens(apps, schema_editor):
    # Plain SQL: the ORM delete loads the rows, which needs the encryption
    # key only to decrypt tokens that are about to be thrown away.
    FitbitToken = apps.get_model('fitbit_integration', 'FitbitToken')
    table = schema_editor.quote_name(FitbitToken._meta.db_table)
    schema_editor.execute(f'DELETE FROM {table}')


class Migration(migrations.Migration):

    dependencies = [
        ('fitbit_integration', '0003_encrypt_tokens_at_rest'),
    ]

    operations = [
        migrations.RunPython(delete_legacy_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='fitbittoken',
            name='fitbit_user_id',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AlterField(
            model_name='fitbittoken',
            name='scope',
            field=models.CharField(
                default='https://www.googleapis.com/auth/googlehealth.sleep.readonly',
                max_length=255,
            ),
        ),
    ]
