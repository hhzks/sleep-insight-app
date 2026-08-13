from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, register


class AiInsightsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_insights'

    def ready(self):
        register(check_stale_window_covers_worst_case)
        register(check_ollama_base_url_has_a_scheme)


def check_ollama_base_url_has_a_scheme(app_configs, **kwargs):
    """OLLAMA_BASE_URL must carry an http:// or https:// scheme.

    Without one, requests raises MissingSchema on every call. That subclasses
    RequestException, so the client reports it as OllamaUnavailable and the
    app degrades to rule-based insights on every generation — a deploy-time
    typo that looks like a server outage and is only visible in the logs.
    """
    base_url = settings.OLLAMA_BASE_URL

    if not base_url.startswith(('http://', 'https://')):
        return [
            Error(
                f'OLLAMA_BASE_URL ({base_url!r}) has no URL scheme. It must start '
                'with http:// or https:// - a self-hosted server behind a TLS '
                'reverse proxy wants https://. Without a scheme, every insight '
                'generation silently falls back to rule-based analysis.',
                id='ai_insights.E002',
            )
        ]
    return []


def check_stale_window_covers_worst_case(app_configs, **kwargs):
    """INSIGHT_JOB_STALE_MINUTES must outlast Celery's hard time limit,

    or the stale-job reaper kills jobs the worker is still legitimately
    running. The hard limit already sits above the worst-case generation
    time, so checking against it covers both. See settings.py and README.md.
    """
    stale_seconds = settings.INSIGHT_JOB_STALE_MINUTES * 60
    hard_limit = settings.INSIGHT_TASK_TIME_LIMIT

    if stale_seconds <= hard_limit:
        return [
            Error(
                f'INSIGHT_JOB_STALE_MINUTES ({settings.INSIGHT_JOB_STALE_MINUTES} min = '
                f'{stale_seconds}s) does not exceed INSIGHT_TASK_TIME_LIMIT '
                f'({hard_limit}s), Celery\'s hard kill for a generation task. The '
                'stale-job reaper will fail jobs the worker is still running. Raise '
                'INSIGHT_JOB_STALE_MINUTES, or lower OLLAMA_TIMEOUT_SECONDS (the task '
                'limits derive from it).',
                id='ai_insights.E001',
            )
        ]
    return []
