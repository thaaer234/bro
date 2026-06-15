import os
import sys
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

sys.stdout.reconfigure(encoding='utf-8')

from django.test import RequestFactory
from students.views import audit_course_api

factory = RequestFactory()
request = factory.get('/students/course-audit/api/', {'student_search': 'غوراني'})

# Add authenticated user
from django.contrib.auth.models import User
request.user = User.objects.filter(is_superuser=True).first()

response = audit_course_api(request)
data = json.loads(response.content)

print(json.dumps(data, indent=2, ensure_ascii=False))
