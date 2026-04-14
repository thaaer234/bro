# api/urls.py
from django.urls import path
from . import views
from accounts import api_views as accounts_api_views

app_name = "api"


urlpatterns = [
    # اختبار الاتصال
    path('test/', views.test_connection, name='test_connection'),
        
    # تسجيل الدخول
    path('auth/student-login/', views.student_parent_login, name='student_login'),
    path('auth/teacher-login/', views.teacher_login, name='teacher_login'),
    path('auth/test/', views.test_auth, name='test_auth'),
    
    # حساب المستخدم
    path('user/profile/update/', views.update_user_profile, name='update_profile'),
    
    # ملف الطالب
    path('student/profile/full/', views.get_student_full_profile, name='student_full_profile'),
    path('student/profile/finance/', accounts_api_views.get_student_finance_profile, name='student_finance_profile_api'),
    
    # ملف المدرس
    path('teacher/profile/full/', views.get_teacher_full_profile, name='teacher_full_profile'),
    path('teacher/students/', views.get_teacher_students, name='teacher_students'),
    path('teacher/performance/', views.get_teacher_performance, name='teacher_performance'),
    
    # الحضور
    path('attendance/record/', views.record_student_attendance, name='record_attendance'),
    
    # طوارئ وإعلانات
    path('emergency/send/', views.send_emergency_alert, name='send_emergency'),
    path('announcements/', views.get_announcements, name='announcements'),
    path('system-report/', views.system_report, name='system_report'),
]
