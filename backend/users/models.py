"""
Custom User Model for Sleep Tracker
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom manager for User model."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user."""
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom User model with Firebase authentication support."""
    
    username = None  # Remove username field
    email = models.EmailField('email address', unique=True)
    firebase_uid = models.CharField(max_length=128, unique=True, null=True, blank=True)
    
    # Profile fields
    display_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    
    # Sleep preferences
    target_sleep_hours = models.DecimalField(
        max_digits=3, decimal_places=1, default=8.0,
        help_text="Target hours of sleep per night"
    )
    target_bedtime = models.TimeField(null=True, blank=True, help_text="Target bedtime")
    target_waketime = models.TimeField(null=True, blank=True, help_text="Target wake time")
    
    # Notification preferences
    enable_sleep_reminders = models.BooleanField(default=True)
    reminder_time = models.TimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    
    objects = UserManager()
    
    def __str__(self):
        return self.email
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
