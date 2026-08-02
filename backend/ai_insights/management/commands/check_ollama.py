"""
Verify that the configured Ollama server is reachable, authenticated, and
serving the expected model. The OCI host firewall and the bearer token are the
two things most likely to be misconfigured, and both fail in ways that are
invisible from inside the app.
"""
import sys
import time

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management.base import BaseCommand

from ai_insights.prompts import INSIGHTS_SCHEMA
from ai_insights.providers.ollama import (
    OllamaAuthError,
    OllamaClient,
    OllamaInvalidResponse,
    OllamaTimeout,
    OllamaUnavailable,
)


class Command(BaseCommand):
    help = 'Check connectivity, auth, and model availability on the Ollama server.'

    def handle(self, *args, **options):
        base_url = settings.OLLAMA_BASE_URL
        model = settings.OLLAMA_MODEL
        has_token = bool(settings.OLLAMA_API_KEY)

        self.stdout.write(f'Server:  {base_url}')
        self.stdout.write(f'Model:   {model}')
        self.stdout.write(f'Token:   {"configured" if has_token else "not set"}')
        self.stdout.write('Sending a test generation...')

        started = time.monotonic()
        try:
            OllamaClient().generate(
                'You are a health assistant. Respond with valid JSON only.',
                'Return a JSON object with overall_assessment "ping", score 50, '
                'an empty insights array, and an empty tips array.',
                INSIGHTS_SCHEMA,
            )
        except ImproperlyConfigured as exc:
            self.stderr.write(f'FAILED: {exc}')
            sys.exit(1)
        except OllamaAuthError as exc:
            if exc.status_code == 403:
                # Caddy's auth rule answers 401, so a 403 means our token was
                # accepted and the rejection came from further in - almost
                # always Ollama refusing a non-local Host header.
                self.stderr.write(
                    f'FAILED: rejected with HTTP 403 ({exc}). Your token was most '
                    'likely ACCEPTED - the reverse proxy answers 401 for a bad '
                    'token. A 403 usually means Ollama itself refused the request '
                    'because the forwarded Host header is not local. Add '
                    '"header_up Host {upstream_hostport}" to the reverse_proxy '
                    'block in your Caddyfile. Confirm on the server with: '
                    'curl -i -H "Host: example.com" http://127.0.0.1:11434/api/tags'
                )
            else:
                self.stderr.write(
                    f'FAILED: the server rejected our token ({exc}). Check that '
                    'OLLAMA_API_KEY matches the token your reverse proxy expects.'
                )
            sys.exit(1)
        except OllamaTimeout as exc:
            self.stderr.write(
                f'FAILED: timed out after {settings.OLLAMA_TIMEOUT_SECONDS}s ({exc}). '
                'The server is reachable but slow — consider a smaller model or a '
                'higher OLLAMA_TIMEOUT_SECONDS.'
            )
            sys.exit(1)
        except OllamaUnavailable as exc:
            self.stderr.write(
                f'FAILED: server unreachable ({exc}). Check the VCN security list, '
                'the host iptables rules, and that Caddy and Ollama are running.'
            )
            sys.exit(1)
        except OllamaInvalidResponse as exc:
            self.stderr.write(
                f'FAILED: server responded but the output was unusable ({exc}). '
                f'Confirm the model "{model}" is pulled: ollama list'
            )
            sys.exit(1)

        elapsed = time.monotonic() - started
        self.stdout.write(self.style.SUCCESS(
            f'OK: {model} at {base_url} responded in {elapsed:.1f}s'
        ))
