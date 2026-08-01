"""
Rule-based insight generation.

This is the fallback whenever the local model is unreachable, too slow, or
returns output that fails validation. It is deliberately dependency-free and
deterministic so it can never itself fail.
"""


def insufficient_data_payload():
    """The payload for a user with no sleep records — the model is never called."""
    return {
        'overall_assessment': (
            'Not enough sleep data to generate insights. Start tracking your sleep '
            'to receive personalized recommendations!'
        ),
        'score': None,
        'insights': [],
        'tips': [
            'Log your sleep manually or connect Fitbit for automatic tracking',
            'Aim for 7-9 hours of sleep per night',
            'Maintain a consistent sleep schedule',
        ],
    }


def generate_rule_based_insights(sleep_summary):
    """Return an insights payload derived from thresholds, not a model."""
    insights = []
    tips = []
    score = 70  # Base score

    avg_sleep = sleep_summary['avg_sleep_hours']
    target = sleep_summary['target_hours']
    efficiency = sleep_summary['avg_efficiency']
    consistency = sleep_summary['consistency_score']

    if avg_sleep < target - 1:
        insights.append({
            'type': 'alert',
            'priority': 'high',
            'title': 'Sleep Duration Below Target',
            'content': (
                f"You're averaging {avg_sleep:.1f} hours of sleep, which is "
                f"{target - avg_sleep:.1f} hours below your {target}-hour target. "
                'Chronic sleep deprivation can affect your health, mood, and '
                'cognitive performance.'
            ),
        })
        tips.append('Try going to bed 30 minutes earlier tonight')
        score -= 15
    elif avg_sleep >= target:
        insights.append({
            'type': 'pattern',
            'priority': 'low',
            'title': 'Meeting Sleep Goals',
            'content': (
                f"Great job! You're averaging {avg_sleep:.1f} hours of sleep, "
                f'meeting or exceeding your {target}-hour target.'
            ),
        })
        score += 10

    if efficiency < 85:
        insights.append({
            'type': 'recommendation',
            'priority': 'medium',
            'title': 'Room for Efficiency Improvement',
            'content': (
                f'Your sleep efficiency is {efficiency:.0f}%, meaning you spend '
                'significant time awake in bed. Consider only going to bed when '
                "truly sleepy and getting up if you can't sleep after 20 minutes."
            ),
        })
        tips.append('Reserve your bed only for sleep - avoid screens and work in bed')
        score -= 10
    elif efficiency >= 90:
        insights.append({
            'type': 'pattern',
            'priority': 'low',
            'title': 'Excellent Sleep Efficiency',
            'content': (
                f'Your sleep efficiency of {efficiency:.0f}% is excellent! '
                'This indicates healthy sleep patterns.'
            ),
        })
        score += 5

    if consistency < 70:
        insights.append({
            'type': 'recommendation',
            'priority': 'medium',
            'title': 'Irregular Sleep Schedule',
            'content': (
                'Your sleep schedule varies significantly from day to day. A '
                'consistent sleep-wake schedule helps regulate your circadian '
                'rhythm and improves sleep quality.'
            ),
        })
        tips.append('Try to go to bed and wake up at the same time every day, even on weekends')
        score -= 10
    elif consistency >= 85:
        score += 5

    if sleep_summary['avg_deep_sleep_minutes'] and sleep_summary['avg_deep_sleep_minutes'] < 45:
        insights.append({
            'type': 'recommendation',
            'priority': 'medium',
            'title': 'Deep Sleep Could Be Better',
            'content': (
                'Your deep sleep duration is below optimal levels. Deep sleep is '
                'crucial for physical recovery. Regular exercise (not too close to '
                'bedtime) can help increase deep sleep.'
            ),
        })
        tips.append('Avoid alcohol before bed - it reduces deep sleep quality')

    if sleep_summary['trend'] == 'declining':
        insights.append({
            'type': 'alert',
            'priority': 'high',
            'title': 'Sleep Quality Declining',
            'content': (
                'Your sleep has been declining over the past week compared to '
                'before. Consider what changes might be affecting your rest.'
            ),
        })
        score -= 10
    elif sleep_summary['trend'] == 'improving':
        insights.append({
            'type': 'pattern',
            'priority': 'low',
            'title': 'Sleep Improving',
            'content': (
                'Your sleep has been improving recently. Keep up the good work '
                "with whatever changes you've made!"
            ),
        })
        score += 5

    if not tips:
        tips = [
            'Maintain a cool, dark, and quiet sleep environment',
            'Avoid caffeine at least 6 hours before bedtime',
            "Create a relaxing bedtime routine to signal your body it's time to sleep",
        ]

    score = max(0, min(100, score))

    if score >= 80:
        assessment = (
            f"Your sleep health is good! You're averaging {avg_sleep:.1f} hours "
            f'with {efficiency:.0f}% efficiency.'
        )
    elif score >= 60:
        assessment = (
            'Your sleep health is moderate. There are opportunities to improve '
            f'your {avg_sleep:.1f}-hour average and {efficiency:.0f}% efficiency.'
        )
    else:
        assessment = (
            f'Your sleep needs attention. With {avg_sleep:.1f} hours average and '
            f'{efficiency:.0f}% efficiency, focused improvements could '
            'significantly benefit your health.'
        )

    return {
        'overall_assessment': assessment,
        'score': score,
        'insights': insights,
        'tips': tips[:3],
    }
