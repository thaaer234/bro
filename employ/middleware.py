from django.utils.deprecation import MiddlewareMixin

class EmployeePermissionsMiddleware(MiddlewareMixin):
    def process_request(self, request):
        perms = set()
        user = request.user
        if user.is_authenticated:
            employee = getattr(user, "employee_profile", None)
            if employee:
                # إذا كان للمستخدم ملف موظف، نقوم بإخفاء حالة السوبر يوزر مؤقتاً في الصفحات الأمامية (وليس في لوحة التحكم الإدارية /admin/)
                # وذلك لتمكين الإدارة من التحكم بكافة صلاحيات السوبر يوزر من لوحة صلاحيات الموظفين
                if not request.path.startswith('/admin/'):
                    user._original_is_superuser = user.is_superuser
                    user.is_superuser = False
                
                perms = set(employee.permissions.filter(is_granted=True)
                            .values_list("permission", flat=True))
            elif user.is_superuser:
                # سوبر يوزر يتجاوز كل شيء إذا لم يكن لديه ملف موظف
                request.employee_permissions = {"__ALL__"}
                return
                
        request.employee_permissions = perms
