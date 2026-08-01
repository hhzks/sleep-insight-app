"""
HTTP client for the self-hosted Ollama server.
"""
import json
from unittest.mock import patch

import requests
from django.test import SimpleTestCase, override_settings

from ai_insights.providers.ollama import (
    OllamaAuthError,
    OllamaClient,
    OllamaInvalidResponse,
    OllamaTimeout,
    OllamaUnavailable,
)


class FakeResponse:
    """Stands in for requests.Response."""

    def __init__(self, status_code=200, body=None, text=''):
        self.status_code = status_code
        self._body = body
        self.text = text

    def json(self):
        if self._body is None:
            raise ValueError('No JSON object could be decoded')
        return self._body


def chat_body(content):
    """Ollama's /api/chat wraps the model's output in message.content."""
    return {'message': {'role': 'assistant', 'content': content}}


GOOD_PAYLOAD = {'overall_assessment': 'ok', 'score': 70, 'insights': [], 'tips': []}


class OllamaClientSuccessTests(SimpleTestCase):
    """A healthy server returns the model's parsed JSON."""

    @patch('ai_insights.providers.ollama.requests.post')
    def test_returns_parsed_json(self, mock_post):
        mock_post.return_value = FakeResponse(body=chat_body(json.dumps(GOOD_PAYLOAD)))
        result = OllamaClient().generate('sys', 'user', {'type': 'object'})
        self.assertEqual(result, GOOD_PAYLOAD)

    @patch('ai_insights.providers.ollama.requests.post')
    def test_sends_model_schema_and_options(self, mock_post):
        mock_post.return_value = FakeResponse(body=chat_body(json.dumps(GOOD_PAYLOAD)))
        schema = {'type': 'object'}
        OllamaClient(model='qwen2.5:3b-instruct', temperature=0.5, num_predict=800).generate(
            'sys', 'user', schema
        )
        sent = mock_post.call_args.kwargs['json']
        self.assertEqual(sent['model'], 'qwen2.5:3b-instruct')
        self.assertFalse(sent['stream'])
        self.assertEqual(sent['format'], schema)
        self.assertEqual(sent['options'], {'temperature': 0.5, 'num_predict': 800})
        self.assertEqual(
            sent['messages'],
            [{'role': 'system', 'content': 'sys'}, {'role': 'user', 'content': 'user'}],
        )

    @patch('ai_insights.providers.ollama.requests.post')
    def test_posts_to_chat_endpoint_without_double_slash(self, mock_post):
        mock_post.return_value = FakeResponse(body=chat_body(json.dumps(GOOD_PAYLOAD)))
        OllamaClient(base_url='https://llm.example.com/').generate('s', 'u', {})
        self.assertEqual(mock_post.call_args.args[0], 'https://llm.example.com/api/chat')


@override_settings(OLLAMA_API_KEY='secret-token')
class OllamaClientAuthHeaderTests(SimpleTestCase):
    """The token is sent when configured and never leaks into errors."""

    @patch('ai_insights.providers.ollama.requests.post')
    def test_sends_authorization_header_when_key_set(self, mock_post):
        mock_post.return_value = FakeResponse(body=chat_body(json.dumps(GOOD_PAYLOAD)))
        OllamaClient().generate('s', 'u', {})
        self.assertEqual(
            mock_post.call_args.kwargs['headers']['Authorization'], 'Bearer secret-token'
        )

    @patch('ai_insights.providers.ollama.requests.post')
    def test_token_absent_from_exception_message(self, mock_post):
        mock_post.return_value = FakeResponse(status_code=401, text='secret-token rejected')
        with self.assertRaises(OllamaAuthError) as ctx:
            OllamaClient().generate('s', 'u', {})
        self.assertNotIn('secret-token', str(ctx.exception))


class OllamaClientNoAuthTests(SimpleTestCase):
    """Local dev runs without a token."""

    @override_settings(OLLAMA_API_KEY='')
    @patch('ai_insights.providers.ollama.requests.post')
    def test_omits_authorization_header_when_key_blank(self, mock_post):
        mock_post.return_value = FakeResponse(body=chat_body(json.dumps(GOOD_PAYLOAD)))
        OllamaClient().generate('s', 'u', {})
        self.assertNotIn('Authorization', mock_post.call_args.kwargs['headers'])


class OllamaClientFailureTests(SimpleTestCase):
    """Every transport and protocol failure maps to a typed error."""

    @patch('ai_insights.providers.ollama.requests.post')
    def test_timeout_raises_ollama_timeout(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout('read timed out')
        with self.assertRaises(OllamaTimeout):
            OllamaClient().generate('s', 'u', {})

    @patch('ai_insights.providers.ollama.requests.post')
    def test_connection_error_raises_unavailable(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError('refused')
        with self.assertRaises(OllamaUnavailable):
            OllamaClient().generate('s', 'u', {})

    @patch('ai_insights.providers.ollama.requests.post')
    def test_403_raises_auth_error(self, mock_post):
        mock_post.return_value = FakeResponse(status_code=403, text='forbidden')
        with self.assertRaises(OllamaAuthError):
            OllamaClient().generate('s', 'u', {})

    @patch('ai_insights.providers.ollama.requests.post')
    def test_500_raises_unavailable(self, mock_post):
        mock_post.return_value = FakeResponse(status_code=500, text='boom')
        with self.assertRaises(OllamaUnavailable):
            OllamaClient().generate('s', 'u', {})

    @patch('ai_insights.providers.ollama.requests.post')
    def test_non_json_envelope_raises_invalid_response(self, mock_post):
        mock_post.return_value = FakeResponse(body=None, text='<html>proxy error</html>')
        with self.assertRaises(OllamaInvalidResponse):
            OllamaClient().generate('s', 'u', {})

    @patch('ai_insights.providers.ollama.requests.post')
    def test_missing_message_content_raises_invalid_response(self, mock_post):
        mock_post.return_value = FakeResponse(body={'done': True})
        with self.assertRaises(OllamaInvalidResponse):
            OllamaClient().generate('s', 'u', {})

    @patch('ai_insights.providers.ollama.requests.post')
    def test_non_json_model_content_raises_invalid_response(self, mock_post):
        mock_post.return_value = FakeResponse(body=chat_body('I cannot help with that.'))
        with self.assertRaises(OllamaInvalidResponse):
            OllamaClient().generate('s', 'u', {})
