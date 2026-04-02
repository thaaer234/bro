# README System Files

هذا الملف هو فهرس شامل لملفات المشروع الحالية داخل النظام، مع تركيز واضح على:
- ملفات النظام الأساسية
- التطبيقات `apps`
- القوالب `templates`
- الملفات الثابتة `static`

ملاحظة:
- هذا الفهرس يعكس الملفات الموجودة حاليًا داخل المشروع.
- توجد بعض ملفات `copy` وملفات طباعة وملفات تجريبية قديمة ما زالت ضمن البنية.

## 1. ملفات الجذر والإعدادات

```text
alyaman/asgi.py
alyaman/firebase.py
alyaman/middleware.py
alyaman/settings.py
alyaman/urls.py
alyaman/wsgi.py
manage.py
README.md
README_SYSTEM_FILES.md
requirements.txt
```

## 2. تطبيق accounts

```text
accounts/accounts_models.py
accounts/admin.py
accounts/api_views.py
accounts/excel_utils.py
accounts/financial_reports_views.py
accounts/forms.py
accounts/forms copy.py
accounts/models.py
accounts/models.py.bak
accounts/site_export_views.py
accounts/urls.py
accounts/views.py
accounts/templatetags/__init__.py
accounts/templatetags/custom_filters.py
accounts/templatetags/formatting.py
accounts/templatetags/number_formatter_tags.py
accounts/templatetags/site_formatting.py
accounts/migrations/__init__.py
accounts/migrations/0001_initial.py
accounts/migrations/0002_initial.py
accounts/migrations/0003_costcenter_actual_annual_spent_and_more.py
accounts/migrations/0004_quickcourseaccounting_quickstudentaccounting.py
accounts/migrations/0005_studentreceipt_quick_enrollment.py
accounts/migrations/0006_costcenter_opening_balance.py
accounts/management/__init__.py
accounts/management/commands/__init__.py
accounts/management/commands/attach_parents.py
accounts/management/commands/auto_assign_teachers.py
accounts/management/commands/backfill_ar_accounts.py
accounts/management/commands/fix_all_entries.py
accounts/management/commands/fix_ar_hierarchy.py
accounts/management/commands/fix_assignments.py
accounts/management/commands/migrate_old_student_ar.py
accounts/management/commands/recalc_account_balances.py
accounts/management/commands/reconcile_student_accounts.py
accounts/management/commands/update_ar_accounts.py
```

## 3. تطبيق announcements

```text
announcements/__init__.py
announcements/admin.py
announcements/apps.py
announcements/context_processors.py
announcements/forms.py
announcements/models.py
announcements/services.py
announcements/urls.py
announcements/views.py
announcements/migrations/__init__.py
announcements/migrations/0001_initial.py
announcements/migrations/0002_rename_indexes.py
announcements/migrations/0003_announcement_action_fields.py
```

## 4. تطبيق api

```text
api/admin.py
api/apps.py
api/auth_backend.py
api/models.py
api/notifications.py
api/serializers.py
api/signals.py
api/urls.py
api/views.py
api/migrations/__init__.py
api/migrations/0001_initial.py
api/migrations/0002_remove_notification_content_type_and_more.py
api/migrations/0003_remove_announcement_api_announc_target__e432a5_idx_and_more.py
api/tests/test_api.py
```

## 5. تطبيق attendance

```text
attendance/admin.py
attendance/apps.py
attendance/form.py
attendance/forms.py
attendance/models.py
attendance/urls.py
attendance/views.py
attendance/templatetags/__init__.py
attendance/templatetags/attendance_filters.py
attendance/templatetags/custom_filters.py
attendance/migrations/__init__.py
attendance/migrations/0001_initial.py
attendance/migrations/0002_add_half_session_count.py
attendance/migrations/0003_remove_teacherattendance_salary_accrual_entry.py
attendance/migrations/0004_alter_teacherattendance_unique_together_and_more.py
attendance/migrations/0005_teacherattendance_branch_backfill.py
```

## 6. تطبيق classroom

```text
classroom/admin.py
classroom/apps.py
classroom/form.py
classroom/models.py
classroom/tests.py
classroom/urls.py
classroom/views.py
classroom/migrations/__init__.py
classroom/migrations/0001_initial.py
classroom/migrations/0002_initial.py
classroom/migrations/0003_classroom_max_capacity_classroom_min_capacity.py
```

## 7. تطبيق core

```text
core/views.py
core/management/commands/resetdb.py
```

## 8. تطبيق courses

```text
courses/admin.py
courses/apps.py
courses/models.py
courses/tests.py
courses/urls.py
courses/views.py
courses/migrations/__init__.py
courses/migrations/0001_initial.py
```

## 9. تطبيق employ

```text
employ/admin.py
employ/apps.py
employ/context_processors.py
employ/decorators.py
employ/forms.py
employ/middleware.py
employ/mixins.py
employ/models.py
employ/services.py
employ/urls.py
employ/utils.py
employ/views.py
employ/templatetags/__init__.py
employ/templatetags/emp_perms.py
employ/templatetags/employ_filters.py
employ/migrations/__init__.py
employ/migrations/0001_initial.py
employ/migrations/0002_teacher_branch.py
employ/migrations/0003_alter_employeepermission_permission.py
employ/migrations/0004_alter_employeepermission_permission_and_more.py
employ/migrations/0005_teacher_hourly_rate_literary_and_more.py
```

## 10. تطبيق errors

```text
errors/__init__.py
errors/admin.py
errors/apps.py
errors/context_processors.py
errors/middleware.py
errors/models.py
errors/security.py
errors/security_middleware.py
errors/security_views.py
errors/tasks.py
errors/urls.py
errors/views.py
errors/migrations/__init__.py
errors/migrations/0001_initial.py
errors/migrations/0002_erroranalytics_securityalert_errorlog_notes_and_more.py
errors/migrations/0003_usertracking_erroranalytics_average_response_time_and_more.py
errors/migrations/0004_securityincident_securityevent_securityblocklist_and_more.py
errors/migrations/0005_securitybranding.py
errors/management/__init__.py
errors/management/commands/__init__.py
errors/management/commands/send_security_report.py
errors/management/commands/send_test_security_email.py
```

## 11. تطبيق exams

```text
exams/admin.py
exams/apps.py
exams/clean_duplicates.py
exams/forms.py
exams/models.py
exams/tests.py
exams/urls.py
exams/views.py
exams/templatetags/__init__.py
exams/templatetags/grade_extras.py
exams/templatetags/grade_filters.py
exams/migrations/__init__.py
exams/migrations/0001_initial.py
exams/migrations/0002_rename_examexams_examgrade_and_more.py
exams/migrations/0003_rename_max_exams_examtype_max_grade_studentexam_and_more.py
```

## 12. تطبيق mobile

```text
mobile/__init__.py
mobile/admin.py
mobile/apps.py
mobile/forms.py
mobile/models.py
mobile/notification_service.py
mobile/signals.py
mobile/urls.py
mobile/utils_notifications.py
mobile/utils_push.py
mobile/views.py
mobile/migrations/__init__.py
mobile/migrations/0001_initial.py
mobile/migrations/0002_listeningtestassignment_grade_and_more.py
mobile/migrations/0003_mobiledevicetoken.py
mobile/migrations/0004_rename_mobiledevi_user_ty_8d20c9_idx_mobile_mobi_user_ty_9178b4_idx_and_more.py
mobile/migrations/0005_listeningtest_max_grade.py
mobile/migrations/0006_mobiledevicetoken_login_role_device_name.py
mobile/migrations/0007_alter_mobiledevicetoken_user_type.py
```

## 13. تطبيق pages

```text
pages/apps.py
pages/email_reports.py
pages/middleware.py
pages/models.py
pages/reporting.py
pages/scheduler.py
pages/signals.py
pages/tests.py
pages/urls.py
pages/views.py
pages/migrations/__init__.py
pages/migrations/0001_initial.py
pages/migrations/0002_system_reports.py
pages/migrations/0003_systemreportuserstats_systemreportusercoursereceipt_and_more.py
pages/migrations/0004_systemreportuserstats_active_hours_and_more.py
pages/migrations/0005_systemreportcoursestats_account_balance_and_more.py
pages/migrations/0006_userclickevent.py
pages/migrations/0007_alter_userclickevent_id.py
pages/migrations/0008_dailyemailreportschedule_activitylog_extra_data_and_more.py
pages/management/__init__.py
pages/management/commands/__init__.py
pages/management/commands/generate_weekly_report.py
pages/management/commands/send_daily_operations_report.py
```

## 14. تطبيق quick

```text
quick/__init__.py
quick/admin.py
quick/apps.py
quick/forms.py
quick/models.py
quick/urls.py
quick/views.py
quick/services/__init__.py
quick/services/receipt_printer.py
quick/migrations/__init__.py
quick/migrations/0001_initial.py
quick/migrations/0002_alter_academicyear_options_alter_quickcourse_options_and_more.py
quick/migrations/0003_quickenrollment_payment_method_and_more.py
quick/migrations/0004_quickstudentreceipt.py
quick/migrations/0005_alter_quickstudentreceipt_amount_and_more.py
quick/migrations/0006_academicyear_is_open_ended.py
quick/migrations/0007_quickstudent_course_track.py
quick/migrations/0008_alter_quickcourse_course_type.py
quick/migrations/0009_quickreceiptprintjob.py
quick/migrations/0010_quickcoursesession_quickcoursesessionenrollment_and_more.py
quick/migrations/0011_quickcoursesession_end_date_and_min_capacity.py
quick/migrations/0012_quickcoursesession_room_and_more.py
quick/management/commands/auto_assign_students.py
```

## 15. تطبيق registration

```text
registration/admin.py
registration/apps.py
registration/forms.py
registration/models.py
registration/services.py
registration/tests.py
registration/urls.py
registration/views.py
registration/migrations/__init__.py
registration/migrations/0001_initial.py
registration/migrations/0002_passwordresetrequest_delete_passwordresetcode.py
registration/migrations/0003_alter_userprofile_profile_picture.py
registration/migrations/0004_alter_userprofile_profile_picture.py
registration/migrations/0005_passwordchangehistory.py
registration/migrations/0006_alter_passwordchangehistory_new_password_hash_and_more.py
registration/migrations/0007_passwordresetrequest_notification_fields.py
```

## 16. تطبيق students

```text
students/admin.py
students/apps.py
students/forms.py
students/models.py
students/urls.py
students/views.py
students/templatetags/__init__.py
students/templatetags/student_filters.py
students/migrations/__init__.py
students/migrations/0001_initial.py
students/migrations/0002_student_academic_year.py
students/migrations/0003_alter_student_options.py
students/migrations/0004_alter_student_options.py
students/migrations/0005_studentwarning.py
students/management/commands/import_students.py
```

## 17. القوالب العامة

```text
templates/base.html
templates/error_base.html
templates/partials/_alerts.html
templates/partials/_navbar.html
```

## 18. قوالب accounts

```text
templates/accounts/account_confirm_delete.html
templates/accounts/account_confirm_delete copy.html
templates/accounts/account_detail.html
templates/accounts/account_detail copy.html
templates/accounts/account_detail copy copy.html
templates/accounts/account_form.html
templates/accounts/account_form copy.html
templates/accounts/account_statement.html
templates/accounts/advance_detail.html
templates/accounts/advance_detail copy.html
templates/accounts/advance_form.html
templates/accounts/advance_form copy.html
templates/accounts/advance_list.html
templates/accounts/advance_list copy.html
templates/accounts/balance_sheet.html
templates/accounts/balance_sheet copy.html
templates/accounts/base.html
templates/accounts/base copy.html
templates/accounts/budget_detail.html
templates/accounts/budget_detail copy.html
templates/accounts/budget_form.html
templates/accounts/budget_form copy.html
templates/accounts/budget_list.html
templates/accounts/budget_list copy.html
templates/accounts/chart_of_accounts.html
templates/accounts/chart_of_accounts copy.html
templates/accounts/chart_of_accounts copy copy.html
templates/accounts/chart_of_accounts copy copy copy.html
templates/accounts/classroom_detail.html
templates/accounts/cost_center_detail.html
templates/accounts/cost_center_detailed_report.html
templates/accounts/cost_center_financial_report.html
templates/accounts/cost_center_form.html
templates/accounts/cost_center_list.html
templates/accounts/course_detail.html
templates/accounts/course_form.html
templates/accounts/course_list.html
templates/accounts/dashboard.html
templates/accounts/employee_financial_overview.html
templates/accounts/employee_financial_profile.html
templates/accounts/expense_detail.html
templates/accounts/income_statement.html
templates/accounts/journal_entry_detail.html
templates/accounts/journal_entry_form.html
templates/accounts/journal_entry_list.html
templates/accounts/ledger.html
templates/accounts/ledger copy.html
templates/accounts/outstanding_course_detail.html
templates/accounts/outstanding_course_students.html
templates/accounts/outstanding_courses.html
templates/accounts/outstanding_students_by_classroom.html
templates/accounts/period_detail.html
templates/accounts/period_form.html
templates/accounts/period_list.html
templates/accounts/receipt_print.html
templates/accounts/receipts_expenses.html
templates/accounts/reports.html
templates/accounts/student_receipt_detail.html
templates/accounts/student_receipt_print.html
templates/accounts/student_receipt_print copy.html
templates/accounts/trial_balance.html
templates/accounts/withdrawn_students.html
templates/accounts/reports/comprehensive_financial.html
templates/accounts/reports/cost_center_analysis.html
templates/accounts/reports/cost_center_cash_flow.html
templates/accounts/reports/cost_center_detail.html
templates/accounts/reports/dashboard.html
templates/accounts/reports/number_formatter_demo.html
templates/accounts/reports/site_export_dashboard.html
templates/accounts/templatetags/number_input.html
```

## 19. قوالب announcements

```text
templates/announcements/dashboard.html
templates/announcements/detail.html
```

## 20. قوالب attendance

```text
templates/attendance/attendance.html
templates/attendance/attendance_detail.html
templates/attendance/attendance_tools.html
templates/attendance/import_teacher_attendance.html
templates/attendance/take_attendance.html
templates/attendance/take_students_attendance.html
templates/attendance/take_students_attendance copy.html
templates/attendance/take_teacher_attendance.html
templates/attendance/teacher_attendance.html
templates/attendance/teacher_attendance_detail.html
templates/attendance/update_attendance.html
templates/attendance/update_teacher_attendance.html
```

## 21. قوالب classroom

```text
templates/classroom/assign_students.html
templates/classroom/assign_to_course.html
templates/classroom/classroom.html
templates/classroom/classroom_cards_print.html
templates/classroom/classroom_confirm_delete.html
templates/classroom/classroom_students.html
templates/classroom/classroom_subject_confirm_delete.html
templates/classroom/classroom_subject_form.html
templates/classroom/classroom_subject_list.html
templates/classroom/create_classroom.html
templates/classroom/update_classroom.html
```

## 22. قوالب courses

```text
templates/courses/courses.html
templates/courses/subject_confirm_delete.html
templates/courses/subject_form.html
templates/courses/subject_list.html
```

## 23. قوالب employ

```text
templates/employ/add_manual_salary.html
templates/employ/employee_advance_detail.html
templates/employ/employee_advance_form.html
templates/employ/employee_advance_list.html
templates/employ/employee_confirm_delete.html
templates/employ/employee_form.html
templates/employ/employee_permissions.html
templates/employ/employee_profile.html
templates/employ/employee_update.html
templates/employ/hr.html
templates/employ/salary_management.html
templates/employ/select_employee.html
templates/employ/teacher_advance_form.html
templates/employ/teacher_advance_list.html
templates/employ/teacher_cards_print.html
templates/employ/teacher_confirm_delete.html
templates/employ/teacher_dashboard.html
templates/employ/teacher_form.html
templates/employ/teacher_profile.html
templates/employ/teachers.html
templates/employ/vacation_form.html
templates/employ/vacation_list.html
```

## 24. قوالب errors و error pages

```text
templates/errors/403.html
templates/errors/404.html
templates/errors/500.html
templates/errors/503.html
templates/errors/analytics.html
templates/errors/dashboard.html
templates/errors/security_alert_email.html
templates/errors/security_alert_email.txt
templates/errors/security_dashboard.html
templates/errors/security_report_email.html
templates/errors/security_report_email.txt
templates/errors/errorlog/map_view.html
```

## 25. قوالب exams

```text
templates/exams/create_exam.html
templates/exams/dashboard.html
templates/exams/delete_exam_confirm.html
templates/exams/edit_exam_grades.html
templates/exams/exam_detail.html
templates/exams/exam_list.html
templates/exams/exam_stats.html
templates/exams/manage_exam_types.html
templates/exams/print_exam_grades.html
templates/exams/select_subject.html
templates/exams/view_exam_grades.html
templates/exams/view_grades.html
```

## 26. قوالب pages

```text
templates/pages/app_users_report.html
templates/pages/index.html
templates/pages/sitemap.html
templates/pages/system_report.html
templates/pages/system_report_print.html
templates/pages/welcome.html
templates/pages/emails/daily_operations_report.html
templates/pages/emails/daily_operations_report.txt
```

## 27. قوالب quick

```text
templates/quick/academic_year_close.html
templates/quick/academic_year_form.html
templates/quick/academic_year_list.html
templates/quick/late_payment_course_detail.html
templates/quick/late_payment_course_list.html
templates/quick/late_payment_course_print.html
templates/quick/outstanding_course_detail.html
templates/quick/outstanding_course_list.html
templates/quick/outstanding_course_print.html
templates/quick/outstanding_course_students.html
templates/quick/quick_accounting_fix_tool.html
templates/quick/quick_classroom_form.html
templates/quick/quick_classroom_list.html
templates/quick/quick_course_attendance_archive.html
templates/quick/quick_course_attendance_dashboard.html
templates/quick/quick_course_conflicts_report.html
templates/quick/quick_course_detail.html
templates/quick/quick_course_form.html
templates/quick/quick_course_list.html
templates/quick/quick_course_schedule_print.html
templates/quick/quick_course_session_attendance.html
templates/quick/quick_course_session_students.html
templates/quick/quick_course_sessions_manage.html
templates/quick/quick_course_time_options_manage.html
templates/quick/quick_duplicate_students_full_print.html
templates/quick/quick_duplicate_students_print.html
templates/quick/quick_duplicate_students_report.html
templates/quick/quick_enrollment_form.html
templates/quick/quick_multiple_receipt_print.html
templates/quick/quick_student_detail.html
templates/quick/quick_student_form.html
templates/quick/quick_student_list.html
templates/quick/quick_student_profile.html
templates/quick/quick_student_receipt_print.html
templates/quick/quick_student_statement.html
templates/quick/quick_student_update.html
templates/quick/quick_withdrawal_fix_tool.html
templates/quick/register_quick_course.html
templates/quick/student_intersections.html
```

## 28. قوالب registration

```text
templates/registration/login.html
templates/registration/password_reset_confirm.html
templates/registration/password_reset_email_action_result.html
templates/registration/password_reset_request.html
templates/registration/profile.html
templates/registration/profile_edit.html
templates/registration/signup.html
templates/registration/superuser_password_reset.html
templates/registration/emails/password_reset_approval.html
templates/registration/emails/password_reset_approval.txt
```

## 29. قوالب students

```text
templates/students/all_regular_students.html
templates/students/base_student.html
templates/students/branch_students.html
templates/students/create_student.html
templates/students/quick_student_form.html
templates/students/quick_student_list.html
templates/students/quick_students.html
templates/students/register_course.html
templates/students/student.html
templates/students/student_cards_print.html
templates/students/student_detailed_report.html
templates/students/student_detailed_report copy.html
templates/students/student_groups.html
templates/students/student_list.html
templates/students/student_profile.html
templates/students/student_search.html
templates/students/student_statement.html
templates/students/student_type_choice.html
templates/students/stunum.html
templates/students/update_student.html
templates/students/partials/_students_table.html
templates/students/partials/_table_filters.html
templates/students/partials/quick_receipt_modal.html
templates/students/partials/refund_modal.html
templates/students/partials/withdraw_modal.html
```

## 30. قوالب mobile

```text
mobile/templates/mobile/about.html
mobile/templates/mobile/login.html
mobile/templates/mobile/notification_detail.html
mobile/templates/mobile/parent_attendance.html
mobile/templates/mobile/parent_base.html
mobile/templates/mobile/parent_dashboard.html
mobile/templates/mobile/parent_finance.html
mobile/templates/mobile/parent_grades.html
mobile/templates/mobile/parent_notifications.html
mobile/templates/mobile/parent_profile.html
mobile/templates/mobile/teacher_base.html
mobile/templates/mobile/teacher_dashboard.html
mobile/templates/mobile/teacher_student_detail.html
mobile/templates/mobile/welcome.html
```

## 31. ملفات static CSS

```text
static/css/accounts-refresh.css
static/css/auth-refresh.css
static/css/main.css
static/css/module-unify-overrides.css
static/css/number-formatter.css
static/css/premium-redesign.css
static/css/pro.css
static/css/responsive.css
static/css/site-unify-overrides.css
static/css/style.css
static/css/style2.css
static/css/ui-refresh.css
static/css/sections/accounts.css
static/css/sections/admin.css
static/css/sections/announcements.css
static/css/sections/attendance.css
static/css/sections/classroom.css
static/css/sections/courses.css
static/css/sections/employ.css
static/css/sections/errors.css
static/css/sections/exams.css
static/css/sections/pages.css
static/css/sections/quick.css
static/css/sections/registration.css
static/css/sections/students.css
static/css/sections/system-rebuild.css
```

## 32. ملفات static JS

```text
static/js/number-formatter.js
static/js/script.js
static/js/student_profile.js
static/js/ui-refresh.js
static/errors/security_telemetry.js
```

## 33. ملفات static images/fonts

```text
static/img/back.png
static/img/back2.png
static/img/logo.png
static/img/logo2.png
static/img/WhatsApp Image 2025-08-25 at 1.20.10 PM.jpeg
static/font/Cairo-400.ttf
static/font/Cairo-600.ttf
static/font/Cairo-800.ttf
static/font/Cocon_ Next Arabic-Bold.otf
```

## 34. ملاحظات تنظيمية

- القوالب الأساسية المعتمدة غالبًا:
  - `templates/base.html`
  - `templates/accounts/base.html`
  - `templates/students/base_student.html`
  - `templates/error_base.html`

- طبقة CSS الحالية تعتمد على:
  - `static/css/premium-redesign.css`
  - `static/css/sections/system-rebuild.css`
  - ملفات القسم داخل `static/css/sections/`

- ملفات فيها نسخ قديمة أو احتياطية:
  - ملفات تحتوي `copy`
  - بعض ملفات `print`
  - `accounts/models.py.bak`

إذا أردت، أستطيع في الخطوة التالية أن أحوّل هذا الفهرس إلى:
- شجرة ملفات `Tree` أوضح
- README مفهرس حسب كل قسم مع وصف وظيفة كل ملف
- ملف توثيق معماري يشرح من يستخدم ماذا داخل النظام
```
