"""
Firebase Authentication for Django REST Framework
"""
import firebase_admin
from firebase_admin import auth, credentials
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings
from .models import User


# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    try:
        if settings.FIREBASE_CONFIG.get('PRIVATE_KEY'):
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.FIREBASE_CONFIG['PROJECT_ID'],
                "private_key": settings.FIREBASE_CONFIG['PRIVATE_KEY'].replace('\\n', '\n'),
                "client_email": settings.FIREBASE_CONFIG['CLIENT_EMAIL'],
                "token_uri": "https://oauth2.googleapis.com/token",
            })
            firebase_admin.initialize_app(cred)
        else:
            # For development, try to use default credentials or skip
            firebase_admin.initialize_app()
    except Exception as e:
        print(f"Warning: Firebase not initialized: {e}")


class FirebaseAuthentication(authentication.BaseAuthentication):
    """
    Firebase Authentication backend for DRF.
    
    Validates Firebase ID tokens and creates/retrieves corresponding Django users.
    """
    
    def authenticate(self, request):
        """Authenticate the request using Firebase ID token."""
        auth_header = request.META.get('HTTP_AUTHORIZATION')
        
        if not auth_header:
            return None
        
        # Check for Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        
        id_token = parts[1]
        
        try:
            # Verify the Firebase ID token
            decoded_token = auth.verify_id_token(id_token)
            firebase_uid = decoded_token['uid']
            email = decoded_token.get('email', '')
            
            # Get or create user
            user, created = User.objects.get_or_create(
                firebase_uid=firebase_uid,
                defaults={
                    'email': email,
                    'display_name': decoded_token.get('name', ''),
                    'avatar_url': decoded_token.get('picture', ''),
                }
            )
            
            # Update user info if changed
            if not created:
                updated = False
                if email and user.email != email:
                    user.email = email
                    updated = True
                if decoded_token.get('name') and user.display_name != decoded_token.get('name'):
                    user.display_name = decoded_token.get('name')
                    updated = True
                if decoded_token.get('picture') and user.avatar_url != decoded_token.get('picture'):
                    user.avatar_url = decoded_token.get('picture')
                    updated = True
                if updated:
                    user.save()
            
            return (user, decoded_token)
            
        except auth.InvalidIdTokenError:
            raise AuthenticationFailed('Invalid Firebase ID token')
        except auth.ExpiredIdTokenError:
            raise AuthenticationFailed('Firebase ID token has expired')
        except auth.RevokedIdTokenError:
            raise AuthenticationFailed('Firebase ID token has been revoked')
        except Exception as e:
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')
    
    def authenticate_header(self, request):
        """Return the WWW-Authenticate header value."""
        return 'Bearer realm="api"'
