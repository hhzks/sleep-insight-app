"""
AI Insights Views
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import SleepInsight, SleepTip
from .services import generate_insights, get_relevant_tips
from .summary import build_sleep_summary
from .serializers import (
    SleepInsightSerializer,
    SleepTipSerializer,
    AIInsightsResponseSerializer,
    InsightFeedbackSerializer
)


class GenerateInsightsView(APIView):
    """Generate AI-powered sleep insights."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Generate new insights based on sleep data."""
        days = request.data.get('days', 30)
        
        try:
            days = int(days)
            days = max(7, min(365, days))
        except (ValueError, TypeError):
            days = 30
        
        insights = generate_insights(request.user, days).payload

        serializer = AIInsightsResponseSerializer(insights)
        return Response(serializer.data)


class InsightsListView(APIView):
    """List saved insights."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user's insights."""
        insights = SleepInsight.objects.filter(user=request.user)
        
        # Filter by read status
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            insights = insights.filter(is_read=is_read.lower() == 'true')
        
        # Filter by type
        insight_type = request.query_params.get('type')
        if insight_type:
            insights = insights.filter(insight_type=insight_type)
        
        # Limit results
        limit = request.query_params.get('limit', 20)
        try:
            limit = int(limit)
        except ValueError:
            limit = 20
        
        insights = insights[:limit]
        serializer = SleepInsightSerializer(insights, many=True)
        return Response(serializer.data)


class InsightDetailView(APIView):
    """View and update a specific insight."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, insight_id):
        """Get a specific insight."""
        try:
            insight = SleepInsight.objects.get(id=insight_id, user=request.user)
        except SleepInsight.DoesNotExist:
            return Response({'error': 'Insight not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Mark as read
        if not insight.is_read:
            insight.is_read = True
            insight.save()
        
        serializer = SleepInsightSerializer(insight)
        return Response(serializer.data)
    
    def patch(self, request, insight_id):
        """Update insight (mark as read, provide feedback)."""
        try:
            insight = SleepInsight.objects.get(id=insight_id, user=request.user)
        except SleepInsight.DoesNotExist:
            return Response({'error': 'Insight not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if 'is_read' in request.data:
            insight.is_read = request.data['is_read']
        
        if 'is_helpful' in request.data:
            insight.is_helpful = request.data['is_helpful']
        
        insight.save()
        
        serializer = SleepInsightSerializer(insight)
        return Response(serializer.data)


class TipsListView(APIView):
    """Get sleep improvement tips."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get relevant tips for the user."""
        limit = request.query_params.get('limit', 5)
        try:
            limit = int(limit)
        except ValueError:
            limit = 5
        
        # Get personalized tips
        tips = get_relevant_tips(request.user, limit)

        serializer = SleepTipSerializer(tips, many=True)
        return Response(serializer.data)


class TipsByCategoryView(APIView):
    """Get tips by category."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, category):
        """Get tips for a specific category."""
        tips = SleepTip.objects.filter(category=category, is_active=True)
        serializer = SleepTipSerializer(tips, many=True)
        return Response(serializer.data)


class QuickInsightsView(APIView):
    """Get quick insights without generating new ones."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get quick sleep summary and insights."""
        # Get sleep summary
        summary = build_sleep_summary(request.user, 7)

        if not summary:
            return Response({
                'has_data': False,
                'message': 'Start tracking your sleep to see insights',
                'summary': None,
                'recent_insights': [],
            })
        
        # Get recent unread insights
        recent_insights = SleepInsight.objects.filter(
            user=request.user,
            is_read=False
        )[:3]
        
        return Response({
            'has_data': True,
            'summary': summary,
            'recent_insights': SleepInsightSerializer(recent_insights, many=True).data,
        })
