"""Liveness endpoint for the platform's health checker.

A plain Django view rather than a DRF one on purpose: REST_FRAMEWORK sets
DEFAULT_PERMISSION_CLASSES to IsAuthenticated, so a DRF view here would 401
the health checker and the machine would be marked unhealthy forever.

This is a liveness check, not a readiness check - it deliberately does not
touch the database. Fly restarts machines that fail it, and a brief Postgres
blip should not cascade into a restart loop of a web process that is fine.
"""
from django.http import JsonResponse


def health(_request):
    return JsonResponse({'status': 'ok'})
