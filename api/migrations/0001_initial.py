# api/migrations/0001_initial.py
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('students', '0001_initial'),
        ('employ', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='MobileUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=100, unique=True, verbose_name='اسم المستخدم')),
                ('password_hash', models.CharField(max_length=128, verbose_name='كلمة المرور المشفرة')),
                ('phone_number', models.CharField(max_length=20, unique=True, verbose_name='رقم الهاتف')),
                ('user_type', models.CharField(choices=[('parent', 'ولي أمر'), ('teacher', 'مدرس'), ('student', 'طالب')], default='parent', max_length=10)),
                ('device_token', models.CharField(blank=True, max_length=255, null=True)),
                ('fcm_token', models.CharField(blank=True, max_length=255, null=True, verbose_name='رمز FCM')),
                ('last_login', models.DateTimeField(blank=True, null=True)),
                ('is_active', models.BooleanField(default=True, verbose_name='نشط')),
                ('is_verified', models.BooleanField(default=False, verbose_name='تم التحقق')),
                ('verification_code', models.CharField(blank=True, max_length=6, null=True)),
                ('profile_image', models.ImageField(blank=True, null=True, upload_to='mobile_profiles/')),
                ('notification_enabled', models.BooleanField(default=True, verbose_name='تمكين الإشعارات')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('django_user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mobile_profile', to='auth.user')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mobile_users', to='students.student')),
                ('teacher', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mobile_users', to='employ.teacher')),
            ],
            options={
                'verbose_name': 'مستخدم الموبايل',
                'verbose_name_plural': 'مستخدمي الموبايل',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['username', 'phone_number'], name='api_mobileu_usernam_d05026_idx'), models.Index(fields=['user_type', 'is_active'], name='api_mobileu_user_ty_e79cee_idx'), models.Index(fields=['last_login'], name='api_mobileu_last_lo_1e5d89_idx')],
            },
        ),
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('announcement', 'إعلان'), ('grade', 'علامة'), ('attendance', 'حضور'), ('behavior', 'سلوك'), ('emergency', 'طارئ'), ('message', 'رسالة')], max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('message', models.TextField()),
                ('object_id', models.PositiveIntegerField(blank=True, null=True)),
                ('is_read', models.BooleanField(default=False, verbose_name='مقروء')),
                ('is_sent', models.BooleanField(default=False, verbose_name='تم الإرسال')),
                ('sent_at', models.DateTimeField(blank=True, null=True, verbose_name='وقت الإرسال')),
                ('data', models.JSONField(blank=True, default=dict, verbose_name='بيانات إضافية')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='api.mobileuser', verbose_name='المستخدم')),
            ],
            options={
                'verbose_name': 'إشعار',
                'verbose_name_plural': 'الإشعارات',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['user', 'is_read'], name='api_notific_user_id_26104a_idx'), models.Index(fields=['notification_type', 'created_at'], name='api_notific_notific_428b7c_idx')],
            },
        ),
        migrations.CreateModel(
            name='EmergencyAlert',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('alert_type', models.CharField(choices=[('emergency', 'حالة طارئة'), ('medical', 'طبي'), ('security', 'أمني'), ('general', 'عام'), ('behavior', 'سلوكي')], default='emergency', max_length=20)),
                ('priority', models.CharField(choices=[('low', 'منخفض'), ('medium', 'متوسط'), ('high', 'عالٍ'), ('critical', 'حرج')], default='medium', max_length=10)),
                ('message', models.TextField(verbose_name='الرسالة')),
                ('location', models.CharField(blank=True, max_length=255, null=True, verbose_name='الموقع')),
                ('latitude', models.FloatField(blank=True, null=True, verbose_name='خط العرض')),
                ('longitude', models.FloatField(blank=True, null=True, verbose_name='خط الطول')),
                ('status', models.CharField(choices=[('pending', 'معلق'), ('active', 'نشط'), ('resolved', 'تم الحل'), ('cancelled', 'ملغي')], default='pending', max_length=20)),
                ('admin_response', models.TextField(blank=True, null=True, verbose_name='رد الإدارة')),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('viewed_by_parent', models.BooleanField(default=False, verbose_name='تمت المشاهدة من ولي الأمر')),
                ('parent_response', models.TextField(blank=True, null=True, verbose_name='رد ولي الأمر')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('responded_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user', verbose_name='تم الرد بواسطة')),
                ('student', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='students.student', verbose_name='الطالب')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='alerts', to='api.mobileuser', verbose_name='المستخدم')),
            ],
            options={
                'verbose_name': 'تنبيه طوارئ',
                'verbose_name_plural': 'تنبيهات الطوارئ',
                'ordering': ['-created_at'],
                'indexes': [models.Index(fields=['user', 'status'], name='api_emergen_user_id_823909_idx'), models.Index(fields=['alert_type', 'priority'], name='api_emergen_alert_t_02e8af_idx'), models.Index(fields=['created_at'], name='api_emergen_created_6cefee_idx')],
            },
        ),
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200, verbose_name='العنوان')),
                ('content', models.TextField(verbose_name='المحتوى')),
                ('target_audience', models.CharField(choices=[('all', 'الجميع'), ('parents', 'أولياء الأمور'), ('students', 'الطلاب'), ('teachers', 'المعلمين'), ('specific_class', 'صف محدد')], default='all', max_length=20)),
                ('category', models.CharField(choices=[('general', 'عام'), ('academic', 'أكاديمي'), ('event', 'فعالية'), ('exam', 'امتحان'), ('holiday', 'عطلة'), ('emergency', 'طارئ')], default='general', max_length=20)),
                ('attachment', models.FileField(blank=True, null=True, upload_to='announcements/', verbose_name='مرفق')),
                ('image', models.ImageField(blank=True, null=True, upload_to='announcements/images/', verbose_name='صورة')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('publish_date', models.DateTimeField(default=django.utils.timezone.now, verbose_name='تاريخ النشر')),
                ('expiration_date', models.DateTimeField(blank=True, null=True, verbose_name='تاريخ الانتهاء')),
                ('is_active', models.BooleanField(default=True, verbose_name='نشط')),
                ('is_important', models.BooleanField(default=False, verbose_name='مهم')),
                ('is_published', models.BooleanField(default=True, verbose_name='منشور')),
                ('requires_acknowledgment', models.BooleanField(default=False, verbose_name='يتطلب إقرار')),
                ('views_count', models.PositiveIntegerField(default=0, verbose_name='عدد المشاهدات')),
                ('classroom', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classroom.classroom', verbose_name='الصف')),
                ('created_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user', verbose_name='أنشأ بواسطة')),
            ],
            options={
                'verbose_name': 'إعلان',
                'verbose_name_plural': 'الإعلانات',
                'ordering': ['-publish_date'],
                'indexes': [models.Index(fields=['target_audience', 'is_active'], name='api_announ_target_849bf5_idx'), models.Index(fields=['category', 'is_important'], name='api_announ_categor_ff76aa_idx'), models.Index(fields=['publish_date'], name='api_announ_publish_1bb082_idx')],
            },
        ),
    ]