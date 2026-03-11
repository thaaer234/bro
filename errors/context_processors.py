from django.utils import timezone
from .models import ErrorLog, SecurityAlert

def error_stats(request):
    """
    معالج سياق لإحصائيات الأخطاء
    """
    try:
        if request.user.is_staff:
            today_errors = ErrorLog.objects.filter(timestamp__date=timezone.now().date()).count()
            unresolved_errors = ErrorLog.objects.filter(resolved=False).count()
            security_alerts = SecurityAlert.objects.filter(resolved=False).count()
            
            return {
                'today_errors_count': today_errors,
                'unresolved_errors_count': unresolved_errors,
                'security_alerts_count': security_alerts,
            }
    except Exception as e:
        # في حالة حدوث أي خطأ، نرجع قامة فارغة
        print(f"Error in context processor: {e}")
    
    return {}