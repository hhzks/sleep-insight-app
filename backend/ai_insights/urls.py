"""
AI Insights URL routes
"""
from django.urls import path
from .views import (
    GenerateInsightsView,
    InsightsListView,
    InsightDetailView,
    TipsListView,
    TipsByCategoryView,
    QuickInsightsView
)

urlpatterns = [
    path('generate/', GenerateInsightsView.as_view(), name='generate-insights'),
    path('list/', InsightsListView.as_view(), name='insights-list'),
    path('<int:insight_id>/', InsightDetailView.as_view(), name='insight-detail'),
    path('tips/', TipsListView.as_view(), name='tips-list'),
    path('tips/<str:category>/', TipsByCategoryView.as_view(), name='tips-by-category'),
    path('quick/', QuickInsightsView.as_view(), name='quick-insights'),
]
