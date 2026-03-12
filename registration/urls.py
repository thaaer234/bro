from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views
from .views import (
    PasswordResetConfirmView,
    PasswordResetEmailActionView,
    PasswordResetRequestView,
    ProfileUpdateView,
    ProfileView,
    SuperUserPasswordResetView,
    registerview,
)


app_name = 'registration'

urlpatterns = [
    path('signup/', registerview.as_view(), name='signup'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/edit/', ProfileUpdateView.as_view(), name='profile_edit'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('superuser-password-reset/', SuperUserPasswordResetView.as_view(), name='superuser_password_reset'),
    path('password-reset-email-action/<str:token>/', PasswordResetEmailActionView.as_view(), name='password_reset_email_action'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
