"""
WSGI config for yaman project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import sys
from django.core.wsgi import get_wsgi_application

# أضف مسار المشروع إلى Python path
path = '/home/Aghead/yaman'
if path not in sys.path:
    sys.path.append(path)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'yaman.settings')

WSGIPassAuthorization = True
application = get_wsgi_application()
