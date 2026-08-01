from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, register


class AiInsightsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_insights'

    def ready(self):
        register(check_stale_window_covers_worst_case)


def check_stale_window_covers_worst_case(app_configs, **kwargs):
    """INSIGHT_JOB_STALE_MINUTES must outlast the worst-case generation time,

    or the stale-job reaper kills jobs that are still legitimately
    generating. See settings.py and README.md for the same invariant.
    """
    stale_seconds = settings.INSIGHT_JOB_STALE_MINUTES * 60
    worst_case = settings.OLLAMA_TIMEOUT_SECONDS * (1 + settings.OLLAMA_INVALID_RETRIES)

    if stale_seconds <= worst_case:
        return [
            Error(
                f'INSIGHT_JOB_STALE_MINUTES ({settings.INSIGHT_JOB_STALE_MINUTES} min = '
                f'{stale_seconds}s) does not exceed OLLAMA_TIMEOUT_SECONDS * '
                f'(1 + OLLAMA_INVALID_RETRIES) ({settings.OLLAMA_TIMEOUT_SECONDS} * '
                f'(1 + {settings.OLLAMA_INVALID_RETRIES}) = {worst_case}s). The stale-job '
                'reaper will kill jobs that are still legitimately generating. Raise '
                'INSIGHT_JOB_STALE_MINUTES to comfortably exceed the worst-case '
                'generation time.',
                id='ai_insights.E001',
            )
        ]
    return []
