from django.contrib.auth.models import User
from django.db import models


class Employee(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="sitemap_employee")
    department = models.CharField(max_length=120)
    role = models.CharField(max_length=120)

    class Meta:
        permissions = [
            ("can_add_student", "Can add student from sitemap"),
            ("can_add_teacher", "Can add teacher from sitemap"),
            ("can_open_reports", "Can open reports from sitemap"),
            ("can_manage_rooms", "Can manage rooms from sitemap"),
        ]

    def __str__(self):
        return f"{self.user.get_username()} - {self.department} - {self.role}"


class ActionLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sitemap_action_logs")
    action_name = models.CharField(max_length=120)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.user.get_username()} - {self.action_name} @ {self.timestamp:%Y-%m-%d %H:%M}"
