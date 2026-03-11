from django.db import migrations


def set_teacherattendance_branch(apps, schema_editor):
    TeacherAttendance = apps.get_model('attendance', 'TeacherAttendance')
    Teacher = apps.get_model('employ', 'Teacher')

    branch_map = {
        'SCIENCE': '\u0639\u0644\u0645\u064a',
        'LITERARY': '\u0623\u062f\u0628\u064a',
        'NINTH': '\u062a\u0627\u0633\u0639',
        'PREPARATORY': '\u062a\u0645\u0647\u064a\u062f\u064a',
    }
    valid_branches = set(branch_map.values())

    qs = TeacherAttendance.objects.select_related('teacher')
    for attendance in qs.iterator():
        teacher = attendance.teacher
        branch_value = None
        branches_field = getattr(teacher, 'branches', '') or ''
        if branches_field:
            candidate = branches_field.split(',')[0].strip()
            if candidate:
                branch_value = branch_map.get(candidate, candidate)
        elif getattr(teacher, 'branch', None):
            branch_value = branch_map.get(teacher.branch)
        if branch_value not in valid_branches:
            branch_value = branch_map['SCIENCE']
        if attendance.branch != branch_value:
            attendance.branch = branch_value
            attendance.save(update_fields=['branch'])


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0004_alter_teacherattendance_unique_together_and_more'),
    ]

    operations = [
        migrations.RunPython(set_teacherattendance_branch, migrations.RunPython.noop),
    ]
