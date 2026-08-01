"""
Validation of model-produced insight payloads.

Constrained decoding makes malformed output rare but not impossible, and a
7B model is likelier to drift than a frontier model. Anything that fails here
is retried once, then falls back to rule-based insights.
"""
from .prompts import INSIGHTS_SCHEMA

_INSIGHT_ITEM = INSIGHTS_SCHEMA['properties']['insights']['items']
VALID_TYPES = _INSIGHT_ITEM['properties']['type']['enum']
VALID_PRIORITIES = _INSIGHT_ITEM['properties']['priority']['enum']

# Mirrors SleepInsight.title's column width (CharField(max_length=255)).
# Enforced here so an over-length title is rejected and retried/falls back
# instead of reaching persist_insights and raising a DB-level DataError.
MAX_TITLE_LENGTH = 255


class InvalidInsightsPayload(Exception):
    """The model returned JSON that does not match the expected shape."""


def validate_insights_payload(payload):
    """Return the payload unchanged, or raise InvalidInsightsPayload."""
    if not isinstance(payload, dict):
        raise InvalidInsightsPayload(f'expected an object, got {type(payload).__name__}')

    for key in ('overall_assessment', 'score', 'insights', 'tips'):
        if key not in payload:
            raise InvalidInsightsPayload(f'missing required key: {key}')

    if not isinstance(payload['overall_assessment'], str):
        raise InvalidInsightsPayload('overall_assessment must be a string')

    score = payload['score']
    # bool is an int subclass in Python, and True would silently pass as 1.
    if not isinstance(score, int) or isinstance(score, bool):
        raise InvalidInsightsPayload('score must be an integer')
    if not 0 <= score <= 100:
        raise InvalidInsightsPayload(f'score out of range: {score}')

    insights = payload['insights']
    if not isinstance(insights, list) or not insights:
        raise InvalidInsightsPayload('insights must be a non-empty array')

    for index, insight in enumerate(insights):
        if not isinstance(insight, dict):
            raise InvalidInsightsPayload(f'insights[{index}] must be an object')
        for key in ('type', 'priority', 'title', 'content'):
            if key not in insight:
                raise InvalidInsightsPayload(f'insights[{index}] missing key: {key}')
            if not isinstance(insight[key], str):
                raise InvalidInsightsPayload(f'insights[{index}].{key} must be a string')
        if len(insight['title']) > MAX_TITLE_LENGTH:
            raise InvalidInsightsPayload(
                f'insights[{index}].title exceeds {MAX_TITLE_LENGTH} characters'
            )
        if insight['type'] not in VALID_TYPES:
            raise InvalidInsightsPayload(f'insights[{index}].type invalid: {insight["type"]}')
        if insight['priority'] not in VALID_PRIORITIES:
            raise InvalidInsightsPayload(
                f'insights[{index}].priority invalid: {insight["priority"]}'
            )

    tips = payload['tips']
    if not isinstance(tips, list):
        raise InvalidInsightsPayload('tips must be an array')
    for index, tip in enumerate(tips):
        if not isinstance(tip, str):
            raise InvalidInsightsPayload(f'tips[{index}] must be a string')

    return payload
