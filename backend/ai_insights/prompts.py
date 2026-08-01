"""
Prompt text and response schema for local model insight generation.

The schema is sent to Ollama as the `format` parameter so decoding is
constrained to a valid shape; validation.py re-checks the result because
constrained decoding is a strong hint, not a guarantee.
"""

SYSTEM_PROMPT = (
    "You are a sleep health expert assistant. Provide helpful, evidence-based "
    "sleep advice. Always respond with valid JSON only, no additional text."
)

INSIGHTS_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_assessment": {"type": "string"},
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "insights": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["pattern", "recommendation", "alert"]},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["type", "priority", "title", "content"],
            },
        },
        "tips": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overall_assessment", "score", "insights", "tips"],
}


def build_insights_prompt(sleep_summary):
    """Render the user-turn prompt from a sleep summary dict."""
    return f"""As a sleep health expert, analyze this user's sleep data and provide personalized insights and recommendations.

Sleep Data Summary (last {sleep_summary['period_days']} days):
- Nights recorded: {sleep_summary['total_records']}
- Average sleep duration: {sleep_summary['avg_sleep_hours']} hours
- Average time in bed: {sleep_summary['avg_time_in_bed_hours']} hours
- Sleep efficiency: {sleep_summary['avg_efficiency']}%
- Deep sleep average: {sleep_summary['avg_deep_sleep_minutes']} minutes
- REM sleep average: {sleep_summary['avg_rem_sleep_minutes']} minutes
- Light sleep average: {sleep_summary['avg_light_sleep_minutes']} minutes
- Sleep consistency score: {sleep_summary['consistency_score']}/100
- Target sleep hours: {sleep_summary['target_hours']} hours
- Accumulated sleep debt: {sleep_summary['sleep_debt_hours']} hours
- Recent trend: {sleep_summary['trend']}

Provide 3-5 insights focused on:
1. Sleep duration analysis
2. Sleep efficiency patterns
3. Sleep stage quality (if available)
4. Consistency and schedule
5. Actionable improvements

The "score" is an overall sleep health score from 0 to 100.
Be encouraging but honest. Focus on specific, actionable advice."""
