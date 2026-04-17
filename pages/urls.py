from django.contrib import admin
from django.urls import path
from django.contrib.auth.decorators import login_required
from . import views
from employ.decorators import require_employee_perm, require_superuser

app_name = "pages"

urlpatterns = [
    path('index', require_employee_perm('admin_dashboard')(views.IndexView.as_view()), name="index"),
    path('', require_employee_perm('admin_dashboard')(views.welcome.as_view()), name="welcome"),
    path('user-guide/', require_superuser(views.UserGuideView.as_view()), name='user_guide'),
    path('user-guide/handbook/', require_superuser(views.UserGuideHandbookView.as_view()), name='user_guide_handbook'),
    path('manual-center/', require_superuser(views.ManualCenterView.as_view()), name='manual_center'),
    path('manual-center/handbook/', require_superuser(views.ManualCenterHandbookView.as_view()), name='manual_center_handbook'),
    path('export-activities/', require_employee_perm('admin_logs')(views.export_activities), name='export_activities'),
    path('sitemap/', login_required(views.sitemap_view), name='sitemap'),
    path('system-report/', require_superuser(views.system_report_dashboard), name='system_report'),
    path('system-report/print/<int:report_id>/', require_superuser(views.system_report_print), name='system_report_print'),
    path('app-users-report/', require_superuser(views.app_users_report), name='app_users_report'),
    path('track-click/', views.track_click_event, name='track_click'),
]   
