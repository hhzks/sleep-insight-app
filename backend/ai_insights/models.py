"""
AI Insights Models
"""
from django.db import models
from django.conf import settings


class SleepInsight(models.Model):
    """Store AI-generated sleep insights."""
    
    INSIGHT_TYPES = [
        ('daily', 'Daily Summary'),
        ('weekly', 'Weekly Analysis'),
        ('monthly', 'Monthly Review'),
        ('pattern', 'Pattern Detection'),
        ('recommendation', 'Recommendation'),
        ('alert', 'Alert'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sleep_insights'
    )
    
    insight_type = models.CharField(max_length=20, choices=INSIGHT_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    
    title = models.CharField(max_length=255)
    content = models.TextField()
    
    # Related data
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    
    # User interaction
    is_read = models.BooleanField(default=False)
    is_helpful = models.BooleanField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sleep_insights'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.title}"


class SleepTip(models.Model):
    """Pre-defined sleep improvement tips."""
    
    CATEGORIES = [
        ('hygiene', 'Sleep Hygiene'),
        ('routine', 'Bedtime Routine'),
        ('environment', 'Sleep Environment'),
        ('lifestyle', 'Lifestyle'),
        ('nutrition', 'Nutrition'),
        ('exercise', 'Exercise'),
        ('stress', 'Stress Management'),
        ('technology', 'Technology'),
    ]
    
    category = models.CharField(max_length=20, choices=CATEGORIES)
    title = models.CharField(max_length=255)
    content = models.TextField()
    short_tip = models.CharField(max_length=255)
    
    # Conditions for showing this tip
    min_sleep_hours = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    max_sleep_hours = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    min_efficiency = models.PositiveIntegerField(null=True, blank=True)
    max_efficiency = models.PositiveIntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sleep_tips'
        ordering = ['order', 'category']
    
    def __str__(self):
        return f"{self.category} - {self.title}"
