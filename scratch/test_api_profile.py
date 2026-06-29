import os
import sys
import json
from decimal import Decimal

# Add project root directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
import django
django.setup()

from api.models import MobileUser
from students.models import Student
from api.views import get_student_full_profile
from accounts.api_views import get_student_finance_profile
from rest_framework.test import APIRequestFactory

# Create mock request
factory = APIRequestFactory()
request = factory.get('/api/student/profile/full/')

# Get mobile user for student 482
mobile_user = MobileUser.objects.get(student_id=482)
request.mobile_user = mobile_user

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

print("=== TESTING get_student_full_profile ===")
try:
    response = get_student_full_profile(request)
    print("Status Code:", response.status_code)
    print("Response Data:")
    print(json.dumps(response.data, indent=2, cls=DecimalEncoder, ensure_ascii=False))
except Exception as e:
    import traceback
    traceback.print_exc()

print("\n=== TESTING get_student_finance_profile ===")
try:
    response_fin = get_student_finance_profile(request)
    print("Status Code:", response_fin.status_code)
    print("Response Data:")
    print(json.dumps(response_fin.data, indent=2, cls=DecimalEncoder, ensure_ascii=False))
except Exception as e:
    import traceback
    traceback.print_exc()
