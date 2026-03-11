from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from .views import (registerview, ProfileView, ProfileUpdateView, 
                   PasswordResetRequestView, SuperUserPasswordResetView,
                   PasswordResetConfirmView)
from django.conf import settings
from django.conf.urls.static import static
from . import views
app_name = 'registration'

urlpatterns = [
    path('signup/', views.registerview.as_view(), name='signup'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileUpdateView.as_view(), name='profile_edit'),
    path('password-reset-request/', views.PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset-confirm/', views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('superuser-password-reset/', views.SuperUserPasswordResetView.as_view(), name='superuser_password_reset'),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)