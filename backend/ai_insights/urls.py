"""
AI Insights URL routes
"""
from django.urls import path
from .views import (
    ActiveInsightJobView,
    GenerateInsightsView,
    InsightJobDetailView,
    InsightsListView,
    InsightDetailView,
    TipsListView,
    TipsByCategoryView,
    QuickInsightsView
)

urlpatterns = [
    path('generate/', GenerateInsightsView.as_view(), name='generate-insights'),
    path('jobs/active/', ActiveInsightJobView.as_view(), name='active-insight-job'),
    path('jobs/<uuid:job_id>/', InsightJobDetailView.as_view(), name='insight-job-detail'),
    path('list/', InsightsListView.as_view(), name='insights-list'),
    path('<int:insight_id>/', InsightDetailView.as_view(), name='insight-detail'),
    path('tips/', TipsListView.as_view(), name='tips-list'),
    path('tips/<str:category>/', TipsByCategoryView.as_view(), name='tips-by-category'),
    path('quick/', QuickInsightsView.as_view(), name='quick-insights'),
]
