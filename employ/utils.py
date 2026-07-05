from typing import Optional
from django.contrib.auth.models import User
from .models import Employee, EmployeePermission

def get_employee_for_user(user: User) -> Optional[Employee]:
    if not user or not user.is_authenticated:
        return None
    # Related name on model: user.employee_profile (as per your Employee model)
    return getattr(user, "employee_profile", None)

def user_has_employee_perm(user: User, code: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    emp = get_employee_for_user(user)
    if emp:
        return emp.permissions.filter(permission=code, is_granted=True).exists()
    if getattr(user, "is_superuser", False) or getattr(user, "_original_is_superuser", False):
        return True
    return False
