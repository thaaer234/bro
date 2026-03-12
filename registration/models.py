from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        print("=== profile save start ===")
        print(f"user: {self.user.username}")
        print(f"has picture: {bool(self.profile_picture)}")

        if self.profile_picture:
            print(f"picture name (pre-save): {self.profile_picture.name}")
            size = None
            try:
                if hasattr(self.profile_picture, "file") and self.profile_picture.file:
                    size = self.profile_picture.file.size
                else:
                    size = self.profile_picture.size
            except FileNotFoundError:
                size = None
            if size is not None:
                print(f"image size: {size} bytes")
            else:
                print("image size: unavailable")

        super().save(*args, **kwargs)

        if self.profile_picture:
            print(f"picture name (post-save): {self.profile_picture.name}")
            if self.profile_picture.name and self.profile_picture.storage.exists(self.profile_picture.name):
                print(f"image path: {self.profile_picture.path}")
            else:
                print("image path: missing file")

        print("=== profile save done ===")

    def get_optimized_picture_url(self):
        if self.profile_picture:
            return self.profile_picture.url
        return None

    def __str__(self):
        return f"{self.user.username} Profile"


class PasswordResetRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_requests')
    reason = models.TextField(verbose_name="سبب الطلب")
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    whatsapp_phone = models.CharField(max_length=32, blank=True, default='')
    is_approved = models.BooleanField(default=False)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    approval_email_sent_at = models.DateTimeField(null=True, blank=True)
    approved_via_email_at = models.DateTimeField(null=True, blank=True)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_delivery_status = models.CharField(max_length=50, blank=True, default='')
    last_notification_error = models.TextField(blank=True, default='')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requests',
    )

    def save(self, *args, **kwargs):
        if self.is_approved and not self.code:
            import secrets

            while True:
                code = secrets.token_hex(3).upper()
                if not PasswordResetRequest.objects.filter(code=code).exists():
                    self.code = code
                    break

        if self.is_approved and not self.expires_at:
            from datetime import timedelta

            self.expires_at = timezone.now() + timedelta(hours=24)

        super().save(*args, **kwargs)

    def is_valid(self):
        return self.is_approved and not self.is_used and self.expires_at and timezone.now() < self.expires_at

    def get_whatsapp_phone(self):
        if self.whatsapp_phone:
            return self.whatsapp_phone

        profile = getattr(self.user, 'profile', None)
        if profile and profile.phone:
            return profile.phone

        return ''

    def get_whatsapp_send_url(self):
        from .services import build_whatsapp_send_url

        return build_whatsapp_send_url(self)

    def __str__(self):
        return f"{self.user.username} - {self.code if self.code else 'Pending'}"


class PasswordChangeHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_history')
    old_password_hash = models.CharField(max_length=128, verbose_name="كلمة المرور القديمة")
    new_password_hash = models.CharField(max_length=128, verbose_name="كلمة المرور الجديدة")
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='changed_passwords',
        verbose_name="تم التغيير بواسطة",
    )
    reset_request = models.ForeignKey(
        PasswordResetRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='password_changes',
    )

    @classmethod
    def create_password_history(cls, user, new_password, changed_by=None, reset_request=None):
        old_password_plain = user.password if user.password else ''
        new_password_plain = new_password

        return cls.objects.create(
            user=user,
            old_password_hash=old_password_plain,
            new_password_hash=new_password_plain,
            changed_by=changed_by,
            reset_request=reset_request,
        )

    def __str__(self):
        return f"{self.user.username} - {self.changed_at.strftime('%Y-%m-%d %H:%M')}"
