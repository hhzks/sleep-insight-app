"""
HTTP client for a self-hosted Ollama server.

In production the base URL points at an HTTPS reverse proxy that checks the
bearer token and forwards to Ollama on localhost, so Ollama itself is never
exposed. Every failure mode is mapped to a typed exception so the caller can
distinguish a dead server from a slow one from a misconfigured token.
"""
import json

import requests
from django.conf import settings


class OllamaError(Exception):
    """Base class for every Ollama failure."""


class OllamaUnavailable(OllamaError):
    """The server could not be reached, or returned a server error."""


class OllamaTimeout(OllamaError):
    """The server did not respond within the configured timeout."""


class OllamaAuthError(OllamaError):
    """The server rejected our credentials — a configuration problem."""


class OllamaInvalidResponse(OllamaError):
    """The server responded, but not with the JSON we expect."""


class OllamaClient:
    """Calls /api/chat on an Ollama server and returns the parsed JSON output."""

    def __init__(
        self,
        base_url=None,
        api_key=None,
        model=None,
        timeout=None,
        temperature=None,
        num_predict=None,
    ):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip('/')
        self.api_key = settings.OLLAMA_API_KEY if api_key is None else api_key
        self.model = model or settings.OLLAMA_MODEL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT_SECONDS
        self.temperature = (
            settings.OLLAMA_TEMPERATURE if temperature is None else temperature
        )
        self.num_predict = num_predict or settings.OLLAMA_NUM_PREDICT

    def generate(self, system_prompt, user_prompt, schema):
        """Return the model's JSON output as a dict, or raise an OllamaError.

        `schema` is passed as Ollama's `format` parameter to constrain decoding.
        """
        headers = {'Content-Type': 'application/json'}
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'

        body = {
            'model': self.model,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
            'stream': False,
            'format': schema,
            'options': {
                'temperature': self.temperature,
                'num_predict': self.num_predict,
            },
        }

        try:
            response = requests.post(
                f'{self.base_url}/api/chat',
                json=body,
                headers=headers,
                timeout=self.timeout,
            )
        # Timeout must be checked first: ConnectTimeout subclasses both.
        except requests.exceptions.Timeout as exc:
            raise OllamaTimeout(f'no response within {self.timeout}s') from exc
        except requests.exceptions.RequestException as exc:
            raise OllamaUnavailable(f'could not reach {self.base_url}') from exc

        # Response text is never interpolated into these messages: on a 401 the
        # proxy may echo the credential back at us.
        if response.status_code in (401, 403):
            raise OllamaAuthError(
                f'server rejected our credentials (HTTP {response.status_code})'
            )
        if response.status_code >= 400:
            raise OllamaUnavailable(f'server returned HTTP {response.status_code}')

        try:
            envelope = response.json()
        except ValueError as exc:
            raise OllamaInvalidResponse('response body was not JSON') from exc

        try:
            content = envelope['message']['content']
        except (KeyError, TypeError) as exc:
            raise OllamaInvalidResponse('response had no message.content') from exc

        try:
            return json.loads(content)
        except (ValueError, TypeError) as exc:
            raise OllamaInvalidResponse('model output was not valid JSON') from exc
