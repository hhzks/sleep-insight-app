"""
Sleep URL routes
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SleepRecordViewSet, SleepGoalViewSet

router = DefaultRouter()
router.register(r'records', SleepRecordViewSet, basename='sleep-record')
router.register(r'goals', SleepGoalViewSet, basename='sleep-goal')

urlpatterns = [
    path('', include(router.urls)),
]
