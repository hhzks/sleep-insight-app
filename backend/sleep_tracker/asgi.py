"""
ASGI config for sleep_tracker project.
"""

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sleep_tracker.settings')
application = get_asgi_application()
