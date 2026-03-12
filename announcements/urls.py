from django.urls import path

from .views import AnnouncementDashboardView, AnnouncementDetailView, dismiss_web_announcement


app_name = "announcements"

urlpatterns = [
    path("", AnnouncementDashboardView.as_view(), name="dashboard"),
    path("<int:pk>/", AnnouncementDetailView.as_view(), name="detail"),
    path("web/<int:announcement_id>/dismiss/", dismiss_web_announcement, name="dismiss_web_announcement"),
]
