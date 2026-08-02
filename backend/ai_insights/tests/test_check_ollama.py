"""
The check_ollama operator diagnostic.
"""
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from ai_insights.providers.ollama import OllamaAuthError, OllamaUnavailable

GOOD = {'overall_assessment': 'ok', 'score': 70, 'insights': [], 'tips': []}


@override_settings(OLLAMA_BASE_URL='https://llm.example.com', OLLAMA_MODEL='qwen2.5:7b-instruct')
class CheckOllamaTests(SimpleTestCase):
    """The command must name the failure so the operator knows what to fix."""

    @patch('ai_insights.management.commands.check_ollama.OllamaClient')
    def test_reports_success_with_the_model_and_url(self, mock_client):
        mock_client.return_value.generate.return_value = GOOD
        out = StringIO()
        call_command('check_ollama', stdout=out)
        output = out.getvalue()
        self.assertIn('OK', output)
        self.assertIn('qwen2.5:7b-instruct', output)
        self.assertIn('https://llm.example.com', output)

    @patch('ai_insights.management.commands.check_ollama.OllamaClient')
    def test_reports_unreachable_server(self, mock_client):
        mock_client.return_value.generate.side_effect = OllamaUnavailable('refused')
        out, err = StringIO(), StringIO()
        with self.assertRaises(SystemExit):
            call_command('check_ollama', stdout=out, stderr=err)
        self.assertIn('unreachable', err.getvalue().lower())

    @patch('ai_insights.management.commands.check_ollama.OllamaClient')
    def test_reports_auth_failure_distinctly(self, mock_client):
        mock_client.return_value.generate.side_effect = OllamaAuthError(
            'rejected', status_code=401
        )
        out, err = StringIO(), StringIO()
        with self.assertRaises(SystemExit):
            call_command('check_ollama', stdout=out, stderr=err)
        self.assertIn('token', err.getvalue().lower())

    @patch('ai_insights.management.commands.check_ollama.OllamaClient')
    def test_403_points_at_the_host_header_not_the_token(self, mock_client):
        """A 403 sends operators hunting for a token problem they do not have.

        Caddy answers 401 for a bad token, so a 403 means the token was
        accepted and Ollama refused the forwarded Host header instead.
        """
        mock_client.return_value.generate.side_effect = OllamaAuthError(
            'server rejected our credentials (HTTP 403)', status_code=403
        )
        out, err = StringIO(), StringIO()
        with self.assertRaises(SystemExit):
            call_command('check_ollama', stdout=out, stderr=err)

        message = err.getvalue()
        self.assertIn('header_up Host', message)
        self.assertIn('ACCEPTED', message)
