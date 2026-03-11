from django.http import HttpResponseForbidden
from django.shortcuts import render
from .utils import user_has_employee_perm
from .models import EmployeePermission 

def require_superuser(view_func):
    def wrapper(request, *args, **kwargs):
        user = request.user
        if user.is_authenticated and user.is_superuser:
            return view_func(request, *args, **kwargs)
        return render(request, 'errors/403.html', {
            'message': 'You do not have permission to access this page.',
            'required_permission': 'superuser',
            'permission_label': 'Superuser'
        }, status=403)
    return wrapper

def require_employee_perm(permission_code):
    """
    ديكوراتير للتحقق من صلاحية الموظف
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if user_has_employee_perm(request.user, permission_code):
                return view_func(request, *args, **kwargs)
            else:
                # عرض صفحة 403 مخصصة
                return render(request, 'errors/403.html', {
                    'message': f'ليس لديك صلاحية للوصول إلى هذه الصفحة.',
                    'required_permission': permission_code,
                    'permission_label': dict(EmployeePermission.PERMISSION_CHOICES).get(permission_code, 'غير معروفة')
                }, status=403)
        return wrapper
    return decorator

def require_employee_perms(permission_codes):
    """
    ديكوراتير للتحقق من عدة صلاحيات
    """
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            for permission_code in permission_codes:
                if user_has_employee_perm(request.user, permission_code):
                    return view_func(request, *args, **kwargs)
            
            # إذا لم توجد أي صلاحية
            return render(request, 'errors/403.html', {
                'message': 'ليس لديك صلاحية للوصول إلى هذه الصفحة.',
                'required_permissions': permission_codes
            }, status=403)
        return wrapper
    return decorator
