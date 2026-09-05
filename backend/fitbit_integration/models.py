"""
Fitbit Integration Models
"""
from django.db import models
from django.conf import settings


class FitbitToken(models.Model):
    """Store Fitbit OAuth tokens for users."""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fitbit_token'
    )
    
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_type = models.CharField(max_length=50, default='Bearer')
    expires_at = models.DateTimeField()
    scope = models.CharField(max_length=255, default='sleep')
    fitbit_user_id = models.CharField(max_length=50, blank=True)

    auto_sync = models.BooleanField(
        default=True,
        help_text="Include this user in the nightly scheduled sync."
    )

    # Reset to 0 by any successful sync. Only FitbitAuthError increments it,
    # so a Fitbit outage cannot disconnect anyone. At
    # FITBIT_MAX_AUTH_FAILURES the token row is deleted, which is exactly
    # what manual disconnection does, so the UI needs no new state.
    consecutive_auth_failures = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fitbit_tokens'
    
    def __str__(self):
        return f"Fitbit Token for {self.user.email}"
    
    @property
    def is_expired(self):
        """Check if token is expired."""
        from django.utils import timezone
        return timezone.now() >= self.expires_at


class FitbitSyncLog(models.Model):
    """Log of Fitbit data syncs."""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fitbit_sync_logs'
    )
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    sync_date = models.DateField()
    records_synced = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'fitbit_sync_logs'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Sync {self.user.email} - {self.sync_date} - {self.status}"
