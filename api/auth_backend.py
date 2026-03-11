# api/auth_backend.py
from .models import MobileUser

class MobileAuthBackend:
    """نظام مصادقة مخصص للـ API"""
    
    def authenticate(self, request, username=None, password=None):
        try:
            user = MobileUser.objects.get(username=username, is_active=True)
            if user.check_password(password):
                user.login()
                return user
        except MobileUser.DoesNotExist:
            return None
        return None
    
    def get_user(self, user_id):
        try:
            return MobileUser.objects.get(pk=user_id, is_active=True)
        except MobileUser.DoesNotExist:
            return None