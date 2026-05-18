"""ASGI config for boisandco project."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'boisandco.settings')
application = get_asgi_application()
