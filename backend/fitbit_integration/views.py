"""
Fitbit Integration Views
"""
import secrets
from datetime import datetime, timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import FitbitToken, FitbitSyncLog
from .services import FitbitError, FitbitService
from .sync import sync_user_sleep
from .serializers import (
    FitbitAuthUrlSerializer,
    FitbitCallbackSerializer,
    FitbitAutoSyncSerializer,
    FitbitConnectionStatusSerializer,
    FitbitSyncSerializer,
    FitbitSyncLogSerializer
)


class FitbitAuthUrlView(APIView):
    """Generate Fitbit authorization URL."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get authorization URL for Fitbit OAuth flow."""
        service = FitbitService()
        
        code_verifier = service.generate_code_verifier()
        code_challenge = service.generate_code_challenge(code_verifier)
        state = secrets.token_urlsafe(32)
        
        auth_url = service.get_authorization_url(code_challenge, state)
        
        data = {
            'authorization_url': auth_url,
            'code_verifier': code_verifier,
            'state': state,
        }
        
        serializer = FitbitAuthUrlSerializer(data)
        return Response(serializer.data)


class FitbitCallbackView(APIView):
    """Handle Fitbit OAuth callback."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Exchange authorization code for tokens."""
        serializer = FitbitCallbackSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        service = FitbitService(user=request.user)
        
        try:
            token_data = service.exchange_code_for_tokens(
                serializer.validated_data['code'],
                serializer.validated_data['code_verifier']
            )
            
            service.save_tokens(token_data)
            
            return Response({
                'message': 'Fitbit connected successfully',
                'fitbit_user_id': token_data.get('user_id', ''),
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class FitbitConnectionStatusView(APIView):
    """Get Fitbit connection status."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Check if user has connected Fitbit."""
        try:
            token = FitbitToken.objects.get(user=request.user)
            last_sync = FitbitSyncLog.objects.filter(
                user=request.user,
                status='success'
            ).first()
            
            data = {
                'connected': True,
                'fitbit_user_id': token.fitbit_user_id,
                'connected_at': token.created_at,
                'last_sync': last_sync.created_at if last_sync else None,
                'auto_sync': token.auto_sync,
            }
        except FitbitToken.DoesNotExist:
            data = {
                'connected': False,
                'fitbit_user_id': '',
                'connected_at': None,
                'last_sync': None,
                # Nothing to sync nightly without a connection.
                'auto_sync': False,
            }
        
        serializer = FitbitConnectionStatusSerializer(data)
        return Response(serializer.data)

    def patch(self, request):
        """Turn the nightly scheduled sync on or off."""
        serializer = FitbitAutoSyncSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = FitbitToken.objects.filter(user=request.user).first()

        if token is None:
            return Response(
                {'error': 'Fitbit is not connected'},
                status=status.HTTP_404_NOT_FOUND,
            )

        token.auto_sync = serializer.validated_data['auto_sync']
        token.save(update_fields=['auto_sync'])

        return Response({'auto_sync': token.auto_sync})
    
    def delete(self, request):
        """Disconnect Fitbit."""
        try:
            FitbitToken.objects.filter(user=request.user).delete()
            return Response({'message': 'Fitbit disconnected successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class FitbitSyncView(APIView):
    """Sync sleep data from Fitbit."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Sync sleep data from Fitbit."""
        serializer = FitbitSyncSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        end_date = serializer.validated_data.get('end_date') or timezone.now().date()
        start_date = serializer.validated_data.get('start_date')

        if not start_date:
            days = serializer.validated_data.get('days', 30)
            start_date = end_date - timedelta(days=days)

        try:
            outcome = sync_user_sleep(request.user, start_date, end_date)
        except FitbitError as exc:
            # sync_user_sleep has already recorded the failure - and, for a
            # rejected authorisation, counted it towards disconnection.
            return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'message': f'Successfully synced {outcome.records_synced} sleep records',
            'records_synced': outcome.records_synced,
            'date_range': {
                'start': outcome.start_date,
                'end': outcome.end_date,
            }
        })


class FitbitSyncLogView(APIView):
    """View sync history."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get sync logs."""
        logs = FitbitSyncLog.objects.filter(user=request.user)[:20]
        serializer = FitbitSyncLogSerializer(logs, many=True)
        return Response(serializer.data)
