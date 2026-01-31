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

from sleep.models import SleepRecord, SleepStageData
from .models import FitbitToken, FitbitSyncLog
from .services import FitbitService, parse_fitbit_sleep_data
from .serializers import (
    FitbitAuthUrlSerializer,
    FitbitCallbackSerializer,
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
            }
        except FitbitToken.DoesNotExist:
            data = {
                'connected': False,
                'fitbit_user_id': '',
                'connected_at': None,
                'last_sync': None,
            }
        
        serializer = FitbitConnectionStatusSerializer(data)
        return Response(serializer.data)
    
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
        
        service = FitbitService(user=request.user)
        
        # Determine date range
        end_date = serializer.validated_data.get('end_date') or timezone.now().date()
        start_date = serializer.validated_data.get('start_date')
        
        if not start_date:
            days = serializer.validated_data.get('days', 30)
            start_date = end_date - timedelta(days=days)
        
        sync_log = FitbitSyncLog.objects.create(
            user=request.user,
            sync_date=end_date,
            status='pending'
        )
        
        try:
            # Fetch sleep data from Fitbit
            sleep_data = service.get_sleep_log_range(
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            
            # Parse and save records
            records = parse_fitbit_sleep_data(sleep_data)
            records_synced = 0
            
            for record_data in records:
                stage_data = record_data.pop('stage_data', [])
                
                # Create or update sleep record
                sleep_record, created = SleepRecord.objects.update_or_create(
                    user=request.user,
                    external_id=record_data['external_id'],
                    defaults={
                        'date_of_sleep': record_data['date_of_sleep'],
                        'start_time': record_data['start_time'],
                        'end_time': record_data['end_time'],
                        'duration_minutes': record_data['duration_minutes'],
                        'minutes_asleep': record_data['minutes_asleep'],
                        'minutes_awake': record_data['minutes_awake'],
                        'efficiency': record_data['efficiency'],
                        'is_main_sleep': record_data['is_main_sleep'],
                        'sleep_type': record_data['sleep_type'],
                        'source': 'fitbit',
                        'deep_sleep_minutes': record_data.get('deep_sleep_minutes'),
                        'light_sleep_minutes': record_data.get('light_sleep_minutes'),
                        'rem_sleep_minutes': record_data.get('rem_sleep_minutes'),
                    }
                )
                
                # Save stage data if available
                if stage_data and created:
                    SleepStageData.objects.filter(sleep_record=sleep_record).delete()
                    for stage in stage_data:
                        SleepStageData.objects.create(
                            sleep_record=sleep_record,
                            stage=stage['stage'],
                            start_time=stage['start_time'],
                            duration_seconds=stage['duration_seconds']
                        )
                
                records_synced += 1
            
            sync_log.status = 'success'
            sync_log.records_synced = records_synced
            sync_log.save()
            
            return Response({
                'message': f'Successfully synced {records_synced} sleep records',
                'records_synced': records_synced,
                'date_range': {
                    'start': start_date,
                    'end': end_date,
                }
            })
            
        except Exception as e:
            sync_log.status = 'failed'
            sync_log.error_message = str(e)
            sync_log.save()
            
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class FitbitSyncLogView(APIView):
    """View sync history."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get sync logs."""
        logs = FitbitSyncLog.objects.filter(user=request.user)[:20]
        serializer = FitbitSyncLogSerializer(logs, many=True)
        return Response(serializer.data)
