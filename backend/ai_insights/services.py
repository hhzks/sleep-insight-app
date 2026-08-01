"""
AI Insights Service
Uses OpenAI or Google Gemini to generate personalized sleep insights.
"""
import json
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone

from .models import SleepInsight, SleepTip
from .rule_based import generate_rule_based_insights, insufficient_data_payload
from .summary import build_sleep_summary


class AIInsightsService:
    """Service for generating AI-powered sleep insights."""
    
    def __init__(self, user):
        self.user = user
        self.openai_api_key = getattr(settings, 'OPENAI_API_KEY', '')
        self.gemini_api_key = getattr(settings, 'GEMINI_API_KEY', '')
        self.ai_provider = getattr(settings, 'AI_PROVIDER', 'openai').lower()
    
    def get_sleep_data_summary(self, days=30):
        """Get a summary of user's sleep data for AI analysis."""
        return build_sleep_summary(self.user, days)
    
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
        return generate_rule_based_insights(sleep_summary)
    
    def generate_and_save_insights(self, days=30):
        """Generate and save insights for the user."""
        sleep_summary = self.get_sleep_data_summary(days)
        
        if not sleep_summary:
            return insufficient_data_payload()
        
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
