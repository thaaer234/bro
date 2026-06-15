import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alyaman.settings')
django.setup()

from django.contrib.auth.models import User

# Check if admin user exists, if not create it, else reset password
username = 'admin_testing'
email = 'admin@test.com'
password = 'Password123'

user, created = User.objects.get_or_create(username=username, defaults={'email': email, 'is_staff': True, 'is_superuser': True})
user.set_password(password)
user.is_staff = True
user.is_superuser = True
user.save()

if created:
    print(f"Superuser '{username}' created with password '{password}'")
else:
    print(f"Superuser '{username}' password reset to '{password}'")
