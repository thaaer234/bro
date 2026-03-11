from django.urls import path
from . import views
from employ.decorators import require_employee_perm

urlpatterns = [
    path('dashboard/', require_employee_perm('admin_logs')(views.error_dashboard), name='error_dashboard'),
    path('analytics/', require_employee_perm('admin_logs')(views.error_analytics_view), name='error_analytics'),
    path('network-analysis/', require_employee_perm('admin_logs')(views.network_analysis_view), name='network_analysis'),
]