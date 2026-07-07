import os
import sys
import django

sys.path.append(os.path.abspath(os.path.dirname(__file__) + '/..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.contrib.auth.models import User
from registration.models import UserProfile

user = User.objects.get(username='thaaer')
profile, _ = UserProfile.objects.get_or_create(user=user)
print(f"User: {user.username}, Phone: '{profile.phone}', Email: '{user.email}'")
