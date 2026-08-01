"""
Insight generation orchestration.

Prefers the self-hosted model and degrades to rule-based analysis on any
failure. The degraded state is always reported: to the user through the job's
`source` field, and to the operator through an error log.
"""
import logging
import time
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import SleepInsight, SleepTip
from .prompts import INSIGHTS_SCHEMA, SYSTEM_PROMPT, build_insights_prompt
from .providers.ollama import (
    OllamaAuthError,
    OllamaClient,
    OllamaInvalidResponse,
    OllamaTimeout,
    OllamaUnavailable,
)
from .rule_based import generate_rule_based_insights, insufficient_data_payload
from .summary import build_sleep_summary
from .validation import InvalidInsightsPayload, validate_insights_payload

logger = logging.getLogger(__name__)

SOURCE_LOCAL_MODEL = 'local_model'
SOURCE_RULE_BASED = 'rule_based'
SOURCE_INSUFFICIENT_DATA = 'insufficient_data'

DEGRADED_NOTICE = (
    'Your AI model was unavailable, so these insights were generated from '
    'built-in rules.'
)

# Maps a provider exception to the error_code stored on the job.
_ERROR_CODES = {
    OllamaTimeout: 'timeout',
    OllamaAuthError: 'auth',
    OllamaUnavailable: 'unreachable',
    OllamaInvalidResponse: 'invalid_response',
}


@dataclass
class InsightsResult:
    """The outcome of one generation attempt."""

    payload: dict
    source: str
    error_code: str = None
    error_detail: str = None


def _error_code_for(exc):
    for exc_type, code in _ERROR_CODES.items():
        if isinstance(exc, exc_type):
            return code
    return 'internal'


def _call_model(provider, sleep_summary):
    """Call the model, retrying once on malformed output.

    Returns the validated payload. Raises the last provider or validation
    error if every attempt fails.
    """
    user_prompt = build_insights_prompt(sleep_summary)
    attempts = 1 + settings.OLLAMA_INVALID_RETRIES
    last_error = None

    for attempt in range(attempts):
        try:
            raw = provider.generate(SYSTEM_PROMPT, user_prompt, INSIGHTS_SCHEMA)
            return validate_insights_payload(raw)
        except InvalidInsightsPayload as exc:
            # Worth retrying: the server is healthy, the model just drifted.
            last_error = OllamaInvalidResponse(str(exc))
            logger.warning(
                'ollama returned malformed output (attempt %s/%s): %s',
                attempt + 1, attempts, exc,
            )
        except OllamaInvalidResponse as exc:
            last_error = exc
            logger.warning(
                'ollama returned unparseable output (attempt %s/%s): %s',
                attempt + 1, attempts, exc,
            )
        # Transport failures (OllamaUnavailable, OllamaTimeout, OllamaAuthError)
        # are deliberately not caught: they will not fix themselves on an
        # immediate retry, so they propagate straight to the fallback.

    raise last_error


def generate_insights(user, days=30, provider=None):
    """Generate insights for a user, persisting them, and report the source."""
    sleep_summary = build_sleep_summary(user, days)
    if sleep_summary is None:
        return InsightsResult(
            payload=insufficient_data_payload(),
            source=SOURCE_INSUFFICIENT_DATA,
        )

    started = time.monotonic()
    try:
        if provider is None:
            provider = OllamaClient()
        payload = _call_model(provider, sleep_summary)
    except Exception as exc:
        error_code = _error_code_for(exc)
        elapsed = time.monotonic() - started
        logger.error(
            'insight generation fell back to rules: code=%s model=%s base_url=%s '
            'elapsed=%.1fs user_id=%s detail=%s',
            error_code,
            settings.OLLAMA_MODEL,
            settings.OLLAMA_BASE_URL,
            elapsed,
            user.id,
            exc,
        )
        payload = generate_rule_based_insights(sleep_summary)
        persist_insights(user, payload, days)
        return InsightsResult(
            payload=payload,
            source=SOURCE_RULE_BASED,
            error_code=error_code,
            error_detail=str(exc),
        )

    logger.info(
        'insight generation succeeded: model=%s elapsed=%.1fs user_id=%s',
        settings.OLLAMA_MODEL, time.monotonic() - started, user.id,
    )
    persist_insights(user, payload, days)
    return InsightsResult(payload=payload, source=SOURCE_LOCAL_MODEL)


def persist_insights(user, payload, days):
    """Write the payload's insights to SleepInsight rows."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)

    for insight in payload.get('insights', []):
        SleepInsight.objects.create(
            user=user,
            insight_type=insight.get('type', 'recommendation'),
            priority=insight.get('priority', 'medium'),
            title=insight.get('title', '')[:255],
            content=insight.get('content', ''),
            start_date=start_date,
            end_date=end_date,
        )


def get_relevant_tips(user, limit=5):
    """Return stored tips filtered against the user's recent sleep stats."""
    sleep_summary = build_sleep_summary(user, 7)
    tips = SleepTip.objects.filter(is_active=True)

    if sleep_summary:
        avg_hours = sleep_summary['avg_sleep_hours']
        efficiency = sleep_summary['avg_efficiency']

        filtered_tips = []
        for tip in tips:
            matches = True
            if tip.min_sleep_hours and avg_hours < float(tip.min_sleep_hours):
                matches = False
            if tip.max_sleep_hours and avg_hours > float(tip.max_sleep_hours):
                matches = False
            if tip.min_efficiency and efficiency < tip.min_efficiency:
                matches = False
            if tip.max_efficiency and efficiency > tip.max_efficiency:
                matches = False
            if matches:
                filtered_tips.append(tip)

        if filtered_tips:
            return filtered_tips[:limit]

    return tips[:limit]
