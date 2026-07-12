from django.urls import path

from .views import (
    ListeningTestAssignmentToggleView,
    MobileDashboardRedirectView,
    MobileDeviceTokenView,
    MobileLoginView,
    MobileLogoutView,
    MobileWelcomeView,
    register_push_token,
    ParentDashboardView,
    ParentAttendanceView,
    ParentFinanceView,
    ParentGradesView,
    ParentNotificationsView,
    ParentProfileView,
    TeacherStudentDetailView,
    TeacherDashboardView,
    MobileTeacherPartnerLedgerView,
    SimulateTeacherMobileView,
)

app_name = "mobile"

urlpatterns = [
    path("", MobileDashboardRedirectView.as_view(), name="dashboard"),
    path("welcome/", MobileWelcomeView.as_view(), name="welcome"),
    path("login/", MobileLoginView.as_view(), name="login"),
    path("device-token/", MobileDeviceTokenView.as_view(), name="device_token"),
    path("register-push-token/", register_push_token, name="register_push_token"),
    
    path("logout/", MobileLogoutView.as_view(), name="logout"),
    path("teacher/", TeacherDashboardView.as_view(), name="teacher_dashboard"),
    path(
        "teacher/simulate/<int:teacher_id>/",
        SimulateTeacherMobileView.as_view(),
        name="simulate_teacher",
    ),
    path(
        "teacher/partner-ledger/<int:account_id>/",
        MobileTeacherPartnerLedgerView.as_view(),
        name="teacher_partner_ledger",
    ),
    path(
        "teacher/student/<int:student_id>/",
        TeacherStudentDetailView.as_view(),
        name="teacher_student_detail",
    ),
    path(
        "teacher/test/<int:test_id>/student/<int:student_id>/toggle/",
        ListeningTestAssignmentToggleView.as_view(),
        name="toggle_test_assignment",
    ),
    path("parent/", ParentDashboardView.as_view(), name="parent_dashboard"),
    path("parent/profile/", ParentProfileView.as_view(), name="parent_profile"),
    path("parent/finance/", ParentFinanceView.as_view(), name="parent_finance"),
    path("parent/attendance/", ParentAttendanceView.as_view(), name="parent_attendance"),
    path("parent/grades/", ParentGradesView.as_view(), name="parent_grades"),
    path(
        "parent/notifications/",
        ParentNotificationsView.as_view(),
        name="parent_notifications",
    ),
]
