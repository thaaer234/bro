from django.db import models
from django.contrib.auth.models import User


class TechnicalReport(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="الموظف")
    job_title = models.CharField(max_length=150, verbose_name="المسمى الوظيفي")
    department = models.CharField(max_length=150, verbose_name="القسم")
    report_date = models.DateField(auto_now_add=True, verbose_name="تاريخ التقرير")
    incident_date = models.DateField(verbose_name="تاريخ وقوع المشكلة")
    report_number = models.CharField(max_length=50, unique=True, blank=True, null=True, verbose_name="رقم التقرير")
    issue_description = models.TextField(verbose_name="وصف المشكلة")
    issue_impact = models.TextField(blank=True, null=True, verbose_name="تأثير المشكلة")
    code_solution = models.TextField(blank=True, null=True, verbose_name="الحل البرمجي المطبق")
    employee_instructions = models.TextField(blank=True, null=True, verbose_name="ما يجب على الموظف القيام به")
    recommendations = models.TextField(blank=True, null=True, verbose_name="توصيات وملاحظات")
    is_resolved = models.BooleanField(default=False, verbose_name="تم الحل")

    class Meta:
        verbose_name = "تقرير مشكلة تقنية"
        verbose_name_plural = "تقارير المشاكل التقنية"
        ordering = ['-report_date', '-id']

    def __str__(self):
        return f"{self.report_number or 'جديد'} - {self.employee.get_full_name() or self.employee.username}"
