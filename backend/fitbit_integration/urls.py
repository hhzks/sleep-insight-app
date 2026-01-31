"""
Fitbit Integration URL routes
"""
from django.urls import path
from .views import (
    FitbitAuthUrlView,
    FitbitCallbackView,
    FitbitConnectionStatusView,
    FitbitSyncView,
    FitbitSyncLogView
)

urlpatterns = [
    path('auth-url/', FitbitAuthUrlView.as_view(), name='fitbit-auth-url'),
    path('callback/', FitbitCallbackView.as_view(), name='fitbit-callback'),
    path('status/', FitbitConnectionStatusView.as_view(), name='fitbit-status'),
    path('sync/', FitbitSyncView.as_view(), name='fitbit-sync'),
    path('sync-logs/', FitbitSyncLogView.as_view(), name='fitbit-sync-logs'),
]
