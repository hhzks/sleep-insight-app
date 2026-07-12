"""
AI Insights Service
Uses OpenAI or Google Gemini to generate personalized sleep insights.
"""
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.db.models import Avg, Count, Sum, Min, Max
from django.utils import timezone

from sleep.models import SleepRecord, SleepGoal
from .models import SleepInsight, SleepTip


class AIInsightsService:
    """Service for generating AI-powered sleep insights."""
    
    def __init__(self, user):
        self.user = user
        self.openai_api_key = getattr(settings, 'OPENAI_API_KEY', '')
        self.gemini_api_key = getattr(settings, 'GEMINI_API_KEY', '')
        self.ai_provider = getattr(settings, 'AI_PROVIDER', 'openai').lower()
    
    def get_sleep_data_summary(self, days=30):
        """Get a summary of user's sleep data for AI analysis."""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        records = SleepRecord.objects.filter(
            user=self.user,
            date_of_sleep__gte=start_date,
            is_main_sleep=True
        ).order_by('date_of_sleep')
        
        if not records.exists():
            return None
        
        # Aggregate statistics
        stats = records.aggregate(
            avg_duration=Avg('duration_minutes'),
            avg_asleep=Avg('minutes_asleep'),
            avg_efficiency=Avg('efficiency'),
            avg_deep=Avg('deep_sleep_minutes'),
            avg_rem=Avg('rem_sleep_minutes'),
            avg_light=Avg('light_sleep_minutes'),
            total_records=Count('id'),
        )
        
        # Calculate sleep consistency (std dev of sleep times)
        sleep_times = []
        for record in records:
            if record.start_time:
                sleep_times.append(record.start_time.hour + record.start_time.minute / 60)
        
        consistency_score = 0
        if len(sleep_times) > 1:
            import statistics
            try:
                std_dev = statistics.stdev(sleep_times)
                consistency_score = max(0, 100 - (std_dev * 20))  # Lower std dev = higher score
            except:
                consistency_score = 50
        
        # Get user's sleep goal
        try:
            goal = SleepGoal.objects.get(user=self.user)
            target_hours = float(goal.target_hours)
        except SleepGoal.DoesNotExist:
            target_hours = 8.0
        
        # Recent trends (last 7 days vs previous 7 days)
        recent_records = records.filter(date_of_sleep__gte=end_date - timedelta(days=7))
        older_records = records.filter(
            date_of_sleep__lt=end_date - timedelta(days=7),
            date_of_sleep__gte=end_date - timedelta(days=14)
        )
        
        recent_avg = recent_records.aggregate(avg=Avg('minutes_asleep'))['avg'] or 0
        older_avg = older_records.aggregate(avg=Avg('minutes_asleep'))['avg'] or 0
        
        trend = 'stable'
        if recent_avg > older_avg * 1.1:
            trend = 'improving'
        elif recent_avg < older_avg * 0.9:
            trend = 'declining'
        
        return {
            'period_days': days,
            'total_records': records.count(),
            'avg_sleep_hours': round((stats['avg_asleep'] or 0) / 60, 2),
            'avg_time_in_bed_hours': round((stats['avg_duration'] or 0) / 60, 2),
            'avg_efficiency': round(stats['avg_efficiency'] or 0, 1),
            'avg_deep_sleep_minutes': round(stats['avg_deep'] or 0, 0),
            'avg_rem_sleep_minutes': round(stats['avg_rem'] or 0, 0),
            'avg_light_sleep_minutes': round(stats['avg_light'] or 0, 0),
            'consistency_score': round(consistency_score, 1),
            'target_hours': target_hours,
            'sleep_debt_hours': round(max(0, (target_hours - (stats['avg_asleep'] or 0) / 60) * days / 7), 1),
            'trend': trend,
        }
    
    def generate_insights_with_ai(self, sleep_summary):
        """Generate insights using configured AI provider (OpenAI or Gemini)."""
        if self.ai_provider == 'gemini' and self.gemini_api_key:
            return self._generate_with_gemini(sleep_summary)
        elif self.openai_api_key:
            return self._generate_with_openai(sleep_summary)
        else:
            return self._generate_rule_based_insights(sleep_summary)
    
    def _get_ai_prompt(self, sleep_summary):
        """Get the common prompt for AI analysis."""
        return f"""As a sleep health expert, analyze this user's sleep data and provide personalized insights and recommendations.

Sleep Data Summary (last {sleep_summary['period_days']} days):
- Average sleep duration: {sleep_summary['avg_sleep_hours']} hours
- Average time in bed: {sleep_summary['avg_time_in_bed_hours']} hours
- Sleep efficiency: {sleep_summary['avg_efficiency']}%
- Deep sleep average: {sleep_summary['avg_deep_sleep_minutes']} minutes
- REM sleep average: {sleep_summary['avg_rem_sleep_minutes']} minutes
- Sleep consistency score: {sleep_summary['consistency_score']}/100
- Target sleep hours: {sleep_summary['target_hours']} hours
- Accumulated sleep debt: {sleep_summary['sleep_debt_hours']} hours
- Recent trend: {sleep_summary['trend']}

Provide a JSON response with the following structure:
{{
    "overall_assessment": "A brief 2-3 sentence assessment of their sleep health",
    "score": 1-100,
    "insights": [
        {{
            "type": "pattern|recommendation|alert",
            "priority": "low|medium|high",
            "title": "Short title",
            "content": "Detailed insight or recommendation (2-3 sentences)"
        }}
    ],
    "tips": [
        "Practical tip 1",
        "Practical tip 2",
        "Practical tip 3"
    ]
}}

Provide 3-5 insights focused on:
1. Sleep duration analysis
2. Sleep efficiency patterns
3. Sleep stage quality (if available)
4. Consistency and schedule
5. Actionable improvements

Be encouraging but honest. Focus on specific, actionable advice."""
    
    def _parse_ai_response(self, content):
        """Parse JSON from AI response, handling markdown code blocks."""
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        return json.loads(content.strip())
    
    def _generate_with_openai(self, sleep_summary):
        """Generate insights using OpenAI API."""
        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_api_key)
            
            prompt = self._get_ai_prompt(sleep_summary)
            
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a sleep health expert assistant. Provide helpful, evidence-based sleep advice. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            return self._parse_ai_response(content)
            
        except Exception as e:
            print(f"OpenAI API error: {e}")
            return self._generate_rule_based_insights(sleep_summary)
    
    def _generate_with_gemini(self, sleep_summary):
        """Generate insights using Google Gemini API."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.gemini_api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            prompt = self._get_ai_prompt(sleep_summary)
            system_instruction = "You are a sleep health expert assistant. Provide helpful, evidence-based sleep advice. Always respond with valid JSON only, no additional text."
            
            response = model.generate_content(
                f"{system_instruction}\n\n{prompt}",
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=1000,
                )
            )
            
            content = response.text
            return self._parse_ai_response(content)
            
        except Exception as e:
            print(f"Gemini API error: {e}")
            return self._generate_rule_based_insights(sleep_summary)
    
    def _generate_rule_based_insights(self, sleep_summary):
        """Generate insights using rule-based logic when AI is unavailable."""
        insights = []
        tips = []
        score = 70  # Base score
        
        avg_sleep = sleep_summary['avg_sleep_hours']
        target = sleep_summary['target_hours']
        efficiency = sleep_summary['avg_efficiency']
        consistency = sleep_summary['consistency_score']
        
        # Sleep duration analysis
        if avg_sleep < target - 1:
            insights.append({
                'type': 'alert',
                'priority': 'high',
                'title': 'Sleep Duration Below Target',
                'content': f"You're averaging {avg_sleep:.1f} hours of sleep, which is {target - avg_sleep:.1f} hours below your {target}-hour target. Chronic sleep deprivation can affect your health, mood, and cognitive performance."
            })
            tips.append("Try going to bed 30 minutes earlier tonight")
            score -= 15
        elif avg_sleep >= target:
            insights.append({
                'type': 'pattern',
                'priority': 'low',
                'title': 'Meeting Sleep Goals',
                'content': f"Great job! You're averaging {avg_sleep:.1f} hours of sleep, meeting or exceeding your {target}-hour target."
            })
            score += 10
        
        # Efficiency analysis
        if efficiency < 85:
            insights.append({
                'type': 'recommendation',
                'priority': 'medium',
                'title': 'Room for Efficiency Improvement',
                'content': f"Your sleep efficiency is {efficiency:.0f}%, meaning you spend significant time awake in bed. Consider only going to bed when truly sleepy and getting up if you can't sleep after 20 minutes."
            })
            tips.append("Reserve your bed only for sleep - avoid screens and work in bed")
            score -= 10
        elif efficiency >= 90:
            insights.append({
                'type': 'pattern',
                'priority': 'low',
                'title': 'Excellent Sleep Efficiency',
                'content': f"Your sleep efficiency of {efficiency:.0f}% is excellent! This indicates healthy sleep patterns."
            })
            score += 5
        
        # Consistency analysis
        if consistency < 70:
            insights.append({
                'type': 'recommendation',
                'priority': 'medium',
                'title': 'Irregular Sleep Schedule',
                'content': "Your sleep schedule varies significantly from day to day. A consistent sleep-wake schedule helps regulate your circadian rhythm and improves sleep quality."
            })
            tips.append("Try to go to bed and wake up at the same time every day, even on weekends")
            score -= 10
        elif consistency >= 85:
            score += 5
        
        # Deep sleep analysis
        if sleep_summary['avg_deep_sleep_minutes'] and sleep_summary['avg_deep_sleep_minutes'] < 45:
            insights.append({
                'type': 'recommendation',
                'priority': 'medium',
                'title': 'Deep Sleep Could Be Better',
                'content': "Your deep sleep duration is below optimal levels. Deep sleep is crucial for physical recovery. Regular exercise (not too close to bedtime) can help increase deep sleep."
            })
            tips.append("Avoid alcohol before bed - it reduces deep sleep quality")
        
        # Trend analysis
        if sleep_summary['trend'] == 'declining':
            insights.append({
                'type': 'alert',
                'priority': 'high',
                'title': 'Sleep Quality Declining',
                'content': "Your sleep has been declining over the past week compared to before. Consider what changes might be affecting your rest."
            })
            score -= 10
        elif sleep_summary['trend'] == 'improving':
            insights.append({
                'type': 'pattern',
                'priority': 'low',
                'title': 'Sleep Improving',
                'content': "Your sleep has been improving recently. Keep up the good work with whatever changes you've made!"
            })
            score += 5
        
        # Ensure we have some tips
        if not tips:
            tips = [
                "Maintain a cool, dark, and quiet sleep environment",
                "Avoid caffeine at least 6 hours before bedtime",
                "Create a relaxing bedtime routine to signal your body it's time to sleep"
            ]
        
        # Ensure score is in valid range
        score = max(0, min(100, score))
        
        # Overall assessment
        if score >= 80:
            assessment = f"Your sleep health is good! You're averaging {avg_sleep:.1f} hours with {efficiency:.0f}% efficiency."
        elif score >= 60:
            assessment = f"Your sleep health is moderate. There are opportunities to improve your {avg_sleep:.1f}-hour average and {efficiency:.0f}% efficiency."
        else:
            assessment = f"Your sleep needs attention. With {avg_sleep:.1f} hours average and {efficiency:.0f}% efficiency, focused improvements could significantly benefit your health."
        
        return {
            'overall_assessment': assessment,
            'score': score,
            'insights': insights,
            'tips': tips[:3]
        }
    
    def generate_and_save_insights(self, days=30):
        """Generate and save insights for the user."""
        sleep_summary = self.get_sleep_data_summary(days)
        
        if not sleep_summary:
            return {
                'overall_assessment': "Not enough sleep data to generate insights. Start tracking your sleep to receive personalized recommendations!",
                'score': None,
                'insights': [],
                'tips': [
                    "Log your sleep manually or connect Fitbit for automatic tracking",
                    "Aim for 7-9 hours of sleep per night",
                    "Maintain a consistent sleep schedule"
                ]
            }
        
        ai_insights = self.generate_insights_with_ai(sleep_summary)
        
        # Save insights to database
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        for insight in ai_insights.get('insights', []):
            SleepInsight.objects.create(
                user=self.user,
                insight_type=insight.get('type', 'recommendation'),
                priority=insight.get('priority', 'medium'),
                title=insight.get('title', ''),
                content=insight.get('content', ''),
                start_date=start_date,
                end_date=end_date,
            )
        
        return ai_insights
    
    def get_relevant_tips(self, limit=5):
        """Get relevant tips based on user's sleep patterns."""
        sleep_summary = self.get_sleep_data_summary(7)
        
        tips = SleepTip.objects.filter(is_active=True)
        
        if sleep_summary:
            avg_hours = sleep_summary['avg_sleep_hours']
            efficiency = sleep_summary['avg_efficiency']
            
            # Filter tips based on conditions
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
