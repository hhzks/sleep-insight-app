"""
URL configuration for sleep_tracker project.
"""
from django.contrib import admin
from django.urls import path, include

from .health import health

urlpatterns = [
    path('api/health/', health),
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/sleep/', include('sleep.urls')),
    path('api/fitbit/', include('fitbit_integration.urls')),
    path('api/insights/', include('ai_insights.urls')),
]
