from django.shortcuts import render ,get_object_or_404 , redirect
from django.views.generic import View , TemplateView ,ListView ,DetailView
from .models import Attendance ,TeacherAttendance
from .form import AttendanceForm,TeacherAttendanceForm
from classroom.models import Classroom
from students.models import Student
from mobile.models import MobileNotification
from mobile.utils_notifications import build_attendance_notification
from employ.models import Teacher
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db import IntegrityError
from django.db.models import Count, F
import pandas as pd
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from django.db import transaction 
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.urls import reverse  
from django.contrib.auth.mixins import LoginRequiredMixin
import json

# Create your views here.

class attendance(ListView):
    model = Attendance
    template_name = 'attendance/attendance.html'
    context_object_name = 'attendance_records'
    
    def get_queryset(self):
        queryset = Attendance.objects.select_related('classroom').order_by('-date')
        branch = self.request.GET.get('branch') or ''
        classroom_id = self.request.GET.get('classroom') or ''
        search = (self.request.GET.get('q') or '').strip()
        month_param = (self.request.GET.get('month') or '').strip()
        if not month_param:
            month_param = timezone.now().date().strftime('%Y-%m')

        if branch:
            queryset = queryset.filter(classroom__branches=branch)
        if classroom_id:
            queryset = queryset.filter(classroom_id=classroom_id)
        if search:
            queryset = queryset.filter(classroom__name__icontains=search)
        if month_param:
            try:
                year_str, month_str = month_param.split('-', 1)
                queryset = queryset.filter(date__year=int(year_str), date__month=int(month_str))
            except ValueError:
                pass

        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        branch = self.request.GET.get('branch') or ''
        classroom_id = self.request.GET.get('classroom') or ''
        search = (self.request.GET.get('q') or '').strip()
        month_param = (self.request.GET.get('month') or '').strip()
        if not month_param:
            month_param = timezone.now().date().strftime('%Y-%m')
        # تجميع التواريخ لكل شعبة
        filtered = self.get_queryset()
        context['summary'] = (filtered.values('classroom_id', 'date')
                                      .annotate(student_count=Count('id'), classroom_name=F('classroom__name'))
                                      .order_by('-date', 'classroom__name'))
        context['branches'] = Classroom.BranchChoices.choices
        context['classrooms'] = Classroom.objects.filter(is_active=True).order_by('name')
        context['months'] = Attendance.objects.dates('date', 'month', order='DESC')
        context['current_month'] = month_param
        context['filters'] = {
            'branch': branch,
            'classroom': classroom_id,
            'q': search,
        }
        return context

class TakeAttendanceView(View):
    template_name = 'attendance/take_attendance.html'
    
    def get(self, request):
        form = AttendanceForm()
        return render(request, self.template_name, {
            'form': form,
            'classrooms': Classroom.objects.all()
        })
    
    def post(self, request):
        date = request.POST.get('date')
        classroom_id = request.POST.get('classroom')
        
        if not date or not classroom_id:
            messages.error(request, 'يجب اختيار التاريخ والشعبة')
            return redirect('attendance:take_attendance')

        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date format.')
            return redirect('attendance:take_attendance')

        classroom = get_object_or_404(Classroom, id=classroom_id)
        students = Student.objects.filter(
            classroom_enrollments__classroom=classroom
        ).distinct()
        
        # التحقق من وجود سجلات قديمة لنفس التاريخ والشعبة
        existing_attendances = Attendance.objects.filter(
            classroom=classroom,
            date=date_obj
        ).exists()
        
        if existing_attendances:
            messages.error(request, 'يوجد بالفعل سجل حضور لهذا التاريخ والشعبة. الرجاء استخدام تعديل الحضور بدلاً من ذلك.')
            return redirect('attendance:take_attendance')
        
        success_count = 0
        error_messages = []
        
        for student in students:
            # قراءة القيمة مباشرة من الـ radio button
            status = request.POST.get(f'status_{student.id}', 'present')  # الافتراضي حاضر
            notes = request.POST.get(f'notes_{student.id}', '')
            
            try:
                attendance = Attendance.objects.create(
                    student=student,
                    classroom=classroom,
                    date=date_obj,
                    status=status,
                    notes=notes
                )
                success_count += 1
            except IntegrityError as e:
                error_messages.append(f'خطأ في تسجيل حضور الطالب {student.full_name}: {str(e)}')
        
        if success_count > 0:
            messages.success(request, f'تم تسجيل حضور {success_count} طالب بنجاح')
        if error_messages:
            messages.error(request, '<br>'.join(error_messages))
        
        return redirect('attendance:attendance')

def get_students(request):
    classroom_id = request.GET.get('classroom')
    
    if not classroom_id:
        return JsonResponse({'error': 'يجب تحديد معرف الشعبة'}, status=400)
    
    try:
        # جلب الطلاب عبر علاقة التسجيل في الشعبة
        students = Student.objects.filter(
            classroom_enrollments__classroom_id=classroom_id
        ).distinct().values('id', 'full_name')
        
        if not students.exists():
            return JsonResponse({'error': 'لا يوجد طلاب في هذه الشعبة'}, status=404)
            
        return JsonResponse(list(students), safe=False)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

class AttendanceDetailView(ListView):
    model = Attendance
    template_name = 'attendance/attendance_detail.html'
    context_object_name = 'attendances'
    
    def get_queryset(self):
        classroom_id = self.kwargs.get('classroom_id')
        date = self.kwargs.get('date')
        return Attendance.objects.filter(classroom_id=classroom_id, date=date)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['classroom'] = get_object_or_404(Classroom, id=self.kwargs.get('classroom_id'))
        context['date'] = self.kwargs.get('date')
        return context

### لتعديل الحضور 
class UpdateAttendanceView(View):
    template_name = 'attendance/update_attendance.html'
    
    def get(self, request, classroom_id, date):
        classroom = get_object_or_404(Classroom, id=classroom_id)
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date format.')
            return redirect('attendance:attendance')

        attendances = Attendance.objects.filter(classroom=classroom, date=date_obj)

        return render(request, self.template_name, {
            'classroom': classroom,
            'date': date_obj,
            'attendances': attendances
        })

    def post(self, request, classroom_id, date):
        classroom = get_object_or_404(Classroom, id=classroom_id)
        students = Student.objects.filter(classroom_enrollments__classroom=classroom)

        try:
            original_date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date format.')
            return redirect('attendance:attendance')

        target_date_str = request.POST.get('date') or date
        try:
            target_date_obj = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date format.')
            return redirect('attendance:attendance')

        if target_date_obj > timezone.now().date():
            messages.error(request, 'Cannot update attendance for a future date.')
            return redirect('attendance:attendance_detail', classroom_id=classroom_id, date=date)

        date_changed = target_date_obj != original_date_obj
        if date_changed:
            conflict_exists = Attendance.objects.filter(
                date=target_date_obj,
                student__in=students
            ).exists()
            if conflict_exists:
                messages.error(request, 'Attendance already exists for some students on this date.')
                return redirect('attendance:attendance_detail', classroom_id=classroom_id, date=date)

        success_count = 0
        error_messages = []

        for student in students:
            # ????? ?????? ?????? ?? ??? radio button
            status = request.POST.get(f'status_{student.id}', 'present')  # ????????? ????
            notes = request.POST.get(f'notes_{student.id}', '')

            try:
                if date_changed:
                    attendance = Attendance.objects.filter(
                        student=student,
                        date=original_date_obj
                    ).first()
                    if attendance:
                        attendance.date = target_date_obj
                        attendance.classroom = classroom
                        attendance.status = status
                        attendance.notes = notes
                        attendance.save()
                    else:
                        Attendance.objects.update_or_create(
                            student=student,
                            date=target_date_obj,
                            defaults={
                                'classroom': classroom,
                                'status': status,
                                'notes': notes
                            }
                        )
                else:
                    Attendance.objects.update_or_create(
                        student=student,
                        date=original_date_obj,
                        defaults={
                            'classroom': classroom,
                            'status': status,
                            'notes': notes
                        }
                    )
                success_count += 1
            except IntegrityError as e:
                error_messages.append(f'??? ?? ????? ???? ?????? {student.full_name}: {str(e)}')

        if success_count > 0:
            messages.success(request, f'تم تحديث حضور {success_count} طالب بنجاح')
        if error_messages:
            messages.error(request, '<br>'.join(error_messages))
        
        return redirect('attendance:attendance')

class DeleteAttendanceView(View):
    def post(self, request, classroom_id, date):
        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date format.')
            return redirect('attendance:attendance')

        if date_obj > timezone.now().date():
            messages.error(request, 'Cannot delete attendance for a future date.')
            return redirect('attendance:attendance_detail', classroom_id=classroom_id, date=date)

        classroom = get_object_or_404(Classroom, id=classroom_id)
        queryset = Attendance.objects.filter(classroom=classroom, date=date_obj)
        record_count = queryset.count()

        if record_count == 0:
            messages.warning(request, 'No attendance records found to delete.')
            return redirect('attendance:attendance_detail', classroom_id=classroom_id, date=date)

        queryset.delete()
        messages.success(request, f'Attendance records deleted ({record_count}).')
        return redirect('attendance:attendance')

from django.db.models import Sum, Count

class TeacherAttendanceView(ListView):
    model = TeacherAttendance
    template_name = 'attendance/teacher_attendance.html'
    context_object_name = 'attendance_records'
    
    def get_queryset(self):
        queryset = TeacherAttendance.objects.select_related('teacher').order_by('-date')
        
        teacher_id = self.request.GET.get('teacher')
        if teacher_id:
            queryset = queryset.filter(teacher_id=teacher_id)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # تجميع البيانات اليومية
        summary = {}
        for record in context['attendance_records']:
            date_key = record.date
            if date_key not in summary:
                summary[date_key] = {
                    'date': record.date,
                    'present_count': 0,
                    'no_duty_count': 0,
                    'total_sessions': 0,
                    'total_half_sessions': 0,
                    'total_combined_sessions': Decimal('0.00'),
                    'salary_amount': Decimal('0.00')
                }
            
            if record.status == 'present':
                summary[date_key]['present_count'] += 1
                summary[date_key]['total_sessions'] += record.session_count
                summary[date_key]['total_half_sessions'] += record.half_session_count
                summary[date_key]['total_combined_sessions'] += record.total_sessions
                summary[date_key]['salary_amount'] += record.get_daily_salary_amount()
            else:
                summary[date_key]['no_duty_count'] += 1
        
        # تحويل إلى قائمة وترتيب
        summary_list = list(summary.values())
        summary_list.sort(key=lambda x: x['date'], reverse=True)
        
        # حساب الإحصائيات الإجمالية
        total_days = len(summary_list)
        total_present = sum(item['present_count'] for item in summary_list)
        total_sessions = sum(item['total_sessions'] for item in summary_list)
        total_half_sessions = sum(item['total_half_sessions'] for item in summary_list)
        total_combined_sessions = sum(item['total_combined_sessions'] for item in summary_list)
        total_salary = sum(item['salary_amount'] for item in summary_list)
        avg_sessions = total_combined_sessions / total_days if total_days > 0 else Decimal('0.00')
        
        context['summary'] = summary_list
        context['teachers'] = Teacher.objects.all()
        context['today'] = timezone.now().date()
        context['total_days'] = total_days
        context['total_present'] = total_present
        context['total_sessions'] = total_sessions
        context['total_half_sessions'] = total_half_sessions
        context['total_combined_sessions'] = float(total_combined_sessions)
        context['total_salary'] = float(total_salary)
        context['avg_sessions'] = float(avg_sessions)
        
        return context

# في views.py - عدل get_context_data
class TakeTeacherAttendanceView(TemplateView):
    template_name = 'attendance/take_teacher_attendance.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        try:
            teachers = Teacher.objects.all().order_by('full_name')
            date_from_url = self.request.GET.get('date')
            default_date = timezone.now().date()
            is_edit_mode = False

            if date_from_url:
                try:
                    default_date = datetime.strptime(date_from_url, '%Y-%m-%d').date()
                    is_edit_mode = True
                except (ValueError, TypeError):
                    default_date = timezone.now().date()
                    is_edit_mode = False

            attendances = list(
                TeacherAttendance.objects.filter(date=default_date).select_related('teacher')
            )
            if attendances:
                is_edit_mode = True
                attendance_dict = {(att.teacher_id, att.branch): att for att in attendances}
            else:
                attendance_dict = {}

            # ????? ?? ??????? dictionary? ?????? list comprehension
            teacher_data = []

            for teacher in teachers:
                branches = self._get_teacher_branches(teacher)
                for branch in branches:
                    branch_code = self._branch_code(branch)
                    teacher_data.append({
                        'teacher': teacher,
                        'branch': branch,
                        'branch_label': self._branch_label(branch),
                        'branch_code': branch_code,
                        'hourly_rate': teacher.get_hourly_rate_for_branch(branch),
                        'attendance': attendance_dict.get((teacher.id, branch)),
                    })
            
            context.update({
                'teacher_data': teacher_data,  # استخدم هذه بدلاً من teachers و existing_attendances
                'default_date': default_date,
                'is_edit_mode': is_edit_mode,
            })
            
        except Exception as e:
            print(f"❌ خطأ في تحميل الصفحة: {e}")
        
        return context
    
    def post(self, request, *args, **kwargs):
        """معالجة بيانات الحضور فقط - بدون قيود محاسبية"""
        try:
            date_str = request.POST.get('date')
            if not date_str:
                messages.error(request, 'يجب اختيار التاريخ')
                return redirect('attendance:take_teacher_attendance')
            
            # تحويل التاريخ
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError) as e:
                messages.error(request, f'تاريخ غير صحيح: {str(e)}')
                return redirect('attendance:take_teacher_attendance')
            
            # منع التواريخ المستقبلية
            if date_obj > timezone.now().date():
                messages.error(request, 'لا يمكن تسجيل حضور لتاريخ مستقبلي')
                return redirect('attendance:take_teacher_attendance')
            
            success_count = 0
            error_messages = []
            teachers_list = list(Teacher.objects.all())
            total_teachers = sum(len(self._get_teacher_branches(t)) for t in teachers_list)
            
            print(f"🔍 بدء معالجة حضور {total_teachers} مدرس ليوم {date_obj}")
            print("=" * 60)
            
            # ✅ استخدام جميع المدرسين من قاعدة البيانات
            for teacher in teachers_list:
                branches = self._get_teacher_branches(teacher)
                for branch in branches:
                    branch_code = self._branch_code(branch)
                    row_key = f"{teacher.id}_{branch_code}"
                    status = request.POST.get(f'status_{row_key}', 'no_duty')
                    session_count_str = request.POST.get(f'sessions_{row_key}', '0')
                    half_session_count_str = request.POST.get(f'half_sessions_{row_key}', '0')
                    notes = request.POST.get(f'notes_{row_key}', '')

                    try:
                        session_count = self._parse_int(session_count_str)
                        half_session_count = self._parse_int(half_session_count_str)

                        if status == 'no_duty':
                            session_count = 0
                            half_session_count = 0

                        attendance, created = TeacherAttendance.objects.update_or_create(
                            teacher=teacher,
                            date=date_obj,
                            branch=branch,
                            defaults={
                                'status': status,
                                'session_count': session_count,
                                'half_session_count': half_session_count,
                                'notes': notes
                            }
                        )

                        print(f"? ?? ??? ???? {teacher.full_name} - {self._branch_label(branch)} - ??????: {attendance.status}")
                        success_count += 1

                    except IntegrityError:
                        error_msg = f"????? ???? ?? {teacher.full_name} - {self._branch_label(branch)}"
                        error_messages.append(error_msg)
                        print(f"?? {error_msg}")

                        try:
                            existing = TeacherAttendance.objects.get(
                                teacher=teacher,
                                date=date_obj,
                                branch=branch
                            )
                            existing.status = status
                            existing.session_count = session_count
                            existing.half_session_count = half_session_count
                            existing.notes = notes
                            existing.save()
                            success_count += 1
                            print(f"?? ?? ????? ????? ??????? ?????? {teacher.full_name} - {self._branch_label(branch)}")
                        except Exception as update_error:
                            error_messages.append(f"??? ?? ????? {teacher.full_name}: {str(update_error)}")

                    except Exception as e:
                        error_msg = f"??? ?? ????? ???? {teacher.full_name}: {str(e)}"
                        error_messages.append(error_msg)
                        print(f"? {error_msg}")

            print("=" * 60)
            print(f"📊 النتائج النهائية:")
            saved_records = TeacherAttendance.objects.filter(date=date_obj).count()
            print(f"   سجلات محفوظة بالفعل لليوم {date_obj}: {saved_records}")
            print(f"   تم محاولة حفظ: {total_teachers}")
            print(f"   نجح: {success_count}")
            print(f"   فشل: {len(error_messages)}")
            print("=" * 60)
            
            # عرض رسائل للمستخدم
            if success_count > 0:
                success_msg = f'تم تسجيل حضور {success_count} مدرس بنجاح ليوم {date_obj}'
                messages.success(request, success_msg)
                
                # إضافة تفاصيل إضافية
                present_count = TeacherAttendance.objects.filter(
                    date=date_obj, 
                    status='present'
                ).count()
                total_sessions = TeacherAttendance.objects.filter(
                    date=date_obj
                ).aggregate(total=Sum('session_count'))['total'] or 0
                
                messages.info(request, f'عدد المدرسين الحاضرين: {present_count} | إجمالي الجلسات: {total_sessions}')
            
            if error_messages:
                messages.warning(request, f'حدثت أخطاء في {len(error_messages)} مدرس')
            
            # إعادة التوجيه
            redirect_url = f"{reverse('attendance:teacher_attendance')}?date={date_obj}"
            return redirect(redirect_url)
            
        except Exception as e:
            messages.error(request, f'حدث خطأ عام: {str(e)}')
            print(f"❌ خطأ عام في تسجيل الحضور: {e}")
            return redirect('attendance:take_teacher_attendance')
        
    def _get_teacher_branches(self, teacher):
        branches = teacher.get_branches_list()
        if not branches and getattr(teacher, 'branch', None):
            branch_map = {
                'SCIENCE': Teacher.BranchChoices.SCIENTIFIC,
                'LITERARY': Teacher.BranchChoices.LITERARY,
                'NINTH': Teacher.BranchChoices.NINTH_GRADE,
                'PREPARATORY': Teacher.BranchChoices.PREPARATORY,
            }
            mapped = branch_map.get(teacher.branch)
            if mapped:
                branches = [mapped]
        return branches or [Teacher.BranchChoices.SCIENTIFIC]

    def _branch_code(self, branch):
        code_map = {
            Teacher.BranchChoices.SCIENTIFIC: 'scientific',
            Teacher.BranchChoices.LITERARY: 'literary',
            Teacher.BranchChoices.NINTH_GRADE: 'ninth',
            Teacher.BranchChoices.PREPARATORY: 'preparatory',
        }
        return code_map.get(branch, 'general')

    def _branch_label(self, branch):
        try:
            return Teacher.BranchChoices(branch).label
        except Exception:
            return branch

    def _parse_int(self, value):
        """تحويل قيمة إلى عدد صحيح"""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0
        
    

def teacher_attendance_by_date(request, date):
    """عرض تفاصيل حضور جميع المدرسين في تاريخ معين"""
    try:
        # تحقق من صحة التاريخ
        from datetime import datetime
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        
        # جلب سجلات الحضور للتاريخ المحدد
        attendances = TeacherAttendance.objects.filter(date=date_obj).select_related('teacher')
        
        # حساب الإحصائيات
        total_teachers = attendances.count()
        present_count = attendances.filter(status='present').count()
        total_sessions = sum(att.session_count for att in attendances)
        total_half_sessions = sum(att.half_session_count for att in attendances)
        total_combined_sessions = sum(float(att.total_sessions) for att in attendances)
        total_salary = sum(float(att.get_daily_salary_amount()) for att in attendances)
        
        context = {
            'date': date_obj,
            'attendances': attendances,
            'total_teachers': total_teachers,
            'present_count': present_count,
            'total_sessions': total_sessions,
            'total_half_sessions': total_half_sessions,
            'total_combined_sessions': total_combined_sessions,
            'total_salary': total_salary,
        }
        return render(request, 'attendance/teacher_attendance_detail.html', context)
        
    except ValueError:
        messages.error(request, 'تاريخ غير صحيح')
        return redirect('attendance:teacher_attendance')

def export_attendance_to_excel(request, classroom_id, date):
    # جلب بيانات الحضور
    attendances = Attendance.objects.filter(
        classroom_id=classroom_id, 
        date=date
    ).select_related('student')
    
    # إنشاء DataFrame من البيانات
    data = []
    for attendance in attendances:
        data.append({
            'اسم الطالب': attendance.student.full_name,
            'الحالة': attendance.get_status_display(),
            'ملاحظات': attendance.notes or ''
        })
    
    df = pd.DataFrame(data)
    
    # إنشاء اسم للملف
    classroom = get_object_or_404(Classroom, id=classroom_id)
    filename = f"حضور_{classroom.name}_{date}.xlsx"
    
    # إنشاء الرد بـ Excel file
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # تصدير DataFrame إلى Excel
    df.to_excel(response, index=False, sheet_name='الحضور')
    
    return response    

class UpdateTeacherAttendanceView(View):
    """تعديل حضور مدرس مع إمكانية تغيير التاريخ"""
    template_name = 'attendance/update_teacher_attendance.html'
    
    def get(self, request, attendance_id):
        attendance = get_object_or_404(TeacherAttendance, id=attendance_id)
        teachers = Teacher.objects.all()
        
        return render(request, self.template_name, {
            'attendance': attendance,
            'teachers': teachers,
            'branches': Teacher.BranchChoices.choices
        })
    
    def post(self, request, attendance_id):
        attendance = get_object_or_404(TeacherAttendance, id=attendance_id)
        
        # حفظ القيم القديمة للمقارنة
        old_session_count = attendance.session_count
        old_half_session_count = attendance.half_session_count
        old_status = attendance.status
        
        # الحصول على البيانات من النموذج
        teacher_id = request.POST.get('teacher')
        branch = request.POST.get('branch')
        date = request.POST.get('date')
        status = request.POST.get('status')
        session_count = request.POST.get('session_count', 0)
        half_session_count = request.POST.get('half_session_count', 0)
        notes = request.POST.get('notes', '')
        
        try:
            # تحويل البيانات
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
            session_count = int(session_count)
            half_session_count = int(half_session_count)
            
            if status == 'no_duty':
                session_count = 0
                half_session_count = 0
            
            # التحقق من عدم وجود تكرار (إذا تم تغيير التاريخ أو المدرس)
            if attendance.teacher_id != int(teacher_id) or attendance.date != date_obj or attendance.branch != branch:
                if TeacherAttendance.objects.filter(
                    teacher_id=teacher_id, 
                    date=date_obj,
                    branch=branch
                ).exclude(id=attendance_id).exists():
                    messages.error(request, 'يوجد بالفعل تسجيل حضور لهذا المدرس في هذا التاريخ')
                    return redirect('attendance:teacher_attendance')
            
            # التحديث
            attendance.teacher_id = teacher_id
            attendance.date = date_obj
            attendance.branch = branch
            attendance.status = status
            attendance.session_count = session_count
            attendance.half_session_count = half_session_count
            attendance.notes = notes
            
            attendance.save()
            
            # رسالة توضح التغيير في الجلسات إذا حدث
            if old_session_count != session_count or old_half_session_count != half_session_count:
                old_total = old_session_count + (old_half_session_count * 0.5)
                new_total = session_count + (half_session_count * 0.5)
                messages.info(request, f'تم تعديل عدد الجلسات من {old_total:.1f} إلى {new_total:.1f}')
            else:
                messages.success(request, 'تم تحديث بيانات الحضور بنجاح')
            
        except Exception as e:
            messages.error(request, f'حدث خطأ أثناء التحديث: {str(e)}')
        
        return redirect('attendance:teacher_attendance')

class DeleteDailyTeacherAttendanceView(View):
    """حذف حضور يوم كامل للمدرسين"""
    
    def post(self, request, date_str):
        try:
            # تحويل التاريخ
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            # التحقق من أن التاريخ ليس في المستقبل
            if date_obj > timezone.now().date():
                messages.error(request, 'لا يمكن حذف حضور لتاريخ مستقبلي')
                return redirect('attendance:teacher_attendance')
            
            # حذف حضور اليوم
            deleted_count = TeacherAttendance.delete_daily_attendance(date_obj)
            
            if deleted_count > 0:
                messages.success(request, f'تم حذف {deleted_count} سجل حضور ليوم {date_str}')
            else:
                messages.warning(request, f'لا توجد سجلات حضور ليوم {date_str}')
                
        except ValueError as e:
            if "مستقبلي" in str(e):
                messages.error(request, str(e))
            else:
                messages.error(request, 'تاريخ غير صحيح')
        except Exception as e:
            print(f"خطأ مفصل في الحذف: {e}")
            messages.error(request, f'حدث خطأ أثناء الحذف: {str(e)}')
        
        return redirect('attendance:teacher_attendance')

@require_POST
@login_required
def delete_daily_attendance_simple(request, date_str):
    """حذف حضور يوم كامل (إصدار مبسط)"""
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # التحقق من التاريخ المستقبلي
        if date_obj > timezone.now().date():
            return JsonResponse({
                'success': False, 
                'error': 'لا يمكن حذف حضور لتاريخ مستقبلي'
            })
        
        # استخدام دالة الحذف من الموديل
        deleted_count = TeacherAttendance.delete_daily_attendance(date_obj)
        
        if deleted_count == 0:
            return JsonResponse({
                'success': False,
                'error': f'لا توجد سجلات حضور ليوم {date_str}'
            })
        
        return JsonResponse({
            'success': True,
            'message': f'تم حذف {deleted_count} سجل حضور ليوم {date_str}'
        })
        
    except ValueError as e:
        if "مستقبلي" in str(e):
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'تاريخ غير صحيح'
            })
    except Exception as e:
        print(f"خطأ مفصل: {e}")
        return JsonResponse({
            'success': False,
            'error': f'حدث خطأ: {str(e)}'
        })

# دوال الاستيراد والتصدير المعدلة
class ImportTeacherAttendanceView(LoginRequiredMixin, View):
    template_name = 'attendance/import_teacher_attendance.html'
    
    def get(self, request):
        # جلب أسماء المدرسين للمساعدة في التصحيح
        teachers = Teacher.objects.all().values_list('full_name', flat=True)
        
        return render(request, self.template_name, {
            'existing_teachers': list(teachers)
        })
    
    def post(self, request):
        if 'json_file' not in request.FILES:
            messages.error(request, 'لم يتم تحميل ملف')
            return redirect('attendance:import_teacher_attendance')
        
        json_file = request.FILES['json_file']
        
        try:
            file_content = json_file.read().decode('utf-8')
            data = json.loads(file_content)
            
            results = self.process_attendance_data(data)
            self.show_detailed_results(request, results)
            
            return redirect('attendance:teacher_attendance')
            
        except json.JSONDecodeError as e:
            messages.error(request, f'ملف JSON غير صحيح: {str(e)}')
        except Exception as e:
            messages.error(request, f'حدث خطأ غير متوقع: {str(e)}')
        
        return redirect('attendance:import_teacher_attendance')
    
    def show_detailed_results(self, request, results):
        """عرض نتائج مفصلة للمستخدم"""
        
        success_msg = f'📊 تم معالجة {results["total_records"]} سجل في الملف | '
        success_msg += f'✅ تم إنشاء {results["created"]} سجلات جديدة | '
        success_msg += f'⏭️ تم تخطي {results["skipped"]} سجلات'
        
        messages.success(request, success_msg)
        
        if results['errors']:
            error_samples = results['errors'][:3]
            for error in error_samples:
                messages.warning(request, f'⚠️ {error}')
        
        if results['missing_teachers']:
            messages.info(request, f'🔍 يوجد {len(results["missing_teachers"])} مدرس يحتاج إضافتهم للنظام')
    
    def process_attendance_data(self, data):
        """معالجة بيانات الحضور من JSON"""
        
        results = {
            'total_records': 0,
            'created': 0,
            'skipped': 0,
            'errors': [],
            'missing_teachers': set(),
            'corrected_names': []
        }
        
        if 'attendance_data' not in data:
            results['errors'].append('هيكل JSON غير صحيح - يجب أن يحتوي على attendance_data')
            return results
        
        attendance_data = data['attendance_data']
        results['total_records'] = len(attendance_data)
        
        for record in attendance_data:
            try:
                result = self.process_single_record(record)
                
                if result['success']:
                    if result['created']:
                        results['created'] += 1
                    else:
                        results['skipped'] += 1
                        
                    if result['name_corrected']:
                        results['corrected_names'].append(result['correction_details'])
                        
                else:
                    results['errors'].append(result['error'])
                    if 'غير موجود' in result['error']:
                        teacher_name = result['error'].split('المدرس ')[1].split(' غير')[0]
                        results['missing_teachers'].add(teacher_name)
                    
            except Exception as e:
                teacher_name = record.get('teacher_name', 'غير معروف')
                results['errors'].append(f'{teacher_name}: {str(e)}')
        
        results['missing_teachers'] = list(results['missing_teachers'])
        
        return results
    
    def process_single_record(self, record):
        """معالجة سجل حضور واحد"""
        
        result = {
            'success': False,
            'created': False,
            'skip_reason': '',
            'error': '',
            'name_corrected': False,
            'correction_details': ''
        }
        
        teacher_name = record.get('teacher_name', '').strip()
        date_str = record.get('date', '')
        total_sessions_input = record.get('total_sessions') or record.get('session_count', 0)
        notes = record.get('notes', '')
        
        if not teacher_name:
            result['error'] = 'اسم المدرس مطلوب'
            return result
        
        if not date_str:
            result['error'] = f'التاريخ مطلوب للمدرس {teacher_name}'
            return result
        
        # البحث عن المدرس
        teacher = self.find_teacher(teacher_name)
        
        if not teacher:
            result['error'] = f'المدرس {teacher_name} غير موجود في النظام'
            return result
        
        # تحويل التاريخ
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            result['error'] = f'تنسيق تاريخ غير صحيح {date_str}'
            return result
        
        if date_obj > timezone.now().date():
            result['error'] = f'لا يمكن تسجيل حضور لتاريخ مستقبلي {date_str}'
            return result
        
        # التحقق إذا كان الحضور مسجل مسبقاً
        branch = self._get_default_branch(teacher)
        existing_attendance = TeacherAttendance.objects.filter(
            teacher=teacher,
            date=date_obj,
            branch=branch
        ).first()
        
        if existing_attendance:
            result['skip_reason'] = f'{teacher.full_name} - {date_obj}'
            result['success'] = True
            return result
        
        # تحليل عدد الجلسات
        session_count, half_session_count = self.parse_sessions_count(total_sessions_input)
        
        # إنشاء سجل الحضور الجديد
        try:
            TeacherAttendance.objects.create(
                teacher=teacher,
                date=date_obj,
                branch=branch,
                status='present',
                session_count=session_count,
                half_session_count=half_session_count,
                notes=notes
            )
            
            result['created'] = True
            result['success'] = True
            
        except Exception as e:
            result['error'] = f'خطأ في حفظ الحضور: {str(e)}'
        
        return result
    
    def find_teacher(self, teacher_name):
        """البحث عن المدرس بطرق مختلفة"""
        # البحث المباشر
        teacher = Teacher.objects.filter(full_name=teacher_name).first()
        if teacher:
            return teacher
        
        # البحث بعد إزالة الأقواس
        clean_name = teacher_name.replace('(', '').replace(')', '').strip()
        teacher = Teacher.objects.filter(full_name=clean_name).first()
        if teacher:
            return teacher
        
        # البحث الجزئي
        teacher = Teacher.objects.filter(full_name__icontains=teacher_name).first()
        if teacher:
            return teacher
        
        # البحث بعد إزالة كلمات التخصص
        specialization_words = ['أدبي', 'ادبي', 'علمي', 'تاسع', 'تمهيدي']
        clean_name = teacher_name
        for word in specialization_words:
            clean_name = clean_name.replace(word, '').strip()
        
        teacher = Teacher.objects.filter(full_name=clean_name).first()
        return teacher
    

    def _get_default_branch(self, teacher):
        branches = teacher.get_branches_list()
        if branches:
            return branches[0]
        if getattr(teacher, 'branch', None):
            branch_map = {
                'SCIENCE': Teacher.BranchChoices.SCIENTIFIC,
                'LITERARY': Teacher.BranchChoices.LITERARY,
                'NINTH': Teacher.BranchChoices.NINTH_GRADE,
                'PREPARATORY': Teacher.BranchChoices.PREPARATORY,
            }
            mapped = branch_map.get(teacher.branch)
            if mapped:
                return mapped
        return Teacher.BranchChoices.SCIENTIFIC

    def parse_sessions_count(self, total_sessions_input):
        """تحليل عدد الجلسات"""
        try:
            if total_sessions_input is None:
                return 0, 0
                
            if isinstance(total_sessions_input, (int, float)):
                total = Decimal(str(total_sessions_input))
            else:
                total = Decimal(str(total_sessions_input))
            
            session_count = int(total)
            fractional_part = total - session_count
            half_session_count = int(round(fractional_part * 2))
            
            if half_session_count > 1:
                session_count += 1
                half_session_count = 0
            
            return session_count, half_session_count
            
        except Exception:
            return 0, 0

class ExportAttendanceTemplateView(LoginRequiredMixin, View):
    """تصدير قالب JSON فارغ"""
    
    def get(self, request):
        template_data = {
            "attendance_data": [
                {
                    "teacher_name": "أحمد محمد",
                    "date": "2024-01-15",
                    "total_sessions": 5.5,
                    "notes": "5 جلسات كاملة + 1 نصف جلسة"
                },
                {
                    "teacher_name": "فاطمة علي", 
                    "date": "2024-01-15",
                    "total_sessions": 3.0,
                    "notes": "3 جلسات كاملة فقط"
                }
            ]
        }
        
        response = JsonResponse(template_data, json_dumps_params={'ensure_ascii': False, 'indent': 2})
        response['Content-Disposition'] = 'attachment; filename="teacher_attendance_template.json"'
        return response

class GetTeachersListView(LoginRequiredMixin, View):
    """الحصول على قائمة جميع المدرسين"""
    
    def get(self, request):
        teachers = Teacher.objects.all().values('id', 'full_name', 'hourly_rate')
        return JsonResponse(list(teachers), safe=False)

class TakeStudentsAttendanceView(View):
    template_name = 'attendance/take_students_attendance.html'
    
    def get(self, request):
        return render(request, self.template_name, {
            'classrooms': Classroom.objects.all(),
            'today': timezone.now().date()
        })
    
    def post(self, request):
        date = request.POST.get('date')
        classroom_id = request.POST.get('classroom')
        
        if not date or not classroom_id:
            messages.error(request, 'يجب اختيار التاريخ والشعبة')
            return redirect('attendance:take_students_attendance')

        try:
            date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            messages.error(request, 'Invalid date format.')
            return redirect('attendance:take_students_attendance')

        classroom = get_object_or_404(Classroom, id=classroom_id)
        students = Student.objects.filter(
            classroom_enrollments__classroom=classroom
        ).distinct()
        
        # التحقق من وجود سجلات قديمة لنفس التاريخ والشعبة
        existing_attendances = Attendance.objects.filter(
            classroom=classroom,
            date=date_obj
        ).exists()
        
        if existing_attendances:
            messages.error(request, 'يوجد بالفعل سجل حضور لهذا التاريخ والشعبة. الرجاء استخدام تعديل الحضور بدلاً من ذلك.')
            return redirect('attendance:take_students_attendance')
        
        success_count = 0
        error_messages = []
        present_count = 0
        
        print("=" * 60)
        print("🔍 بدء معالجة حضور الطلاب:")
        print(f"📅 التاريخ: {date}")
        print(f"🏫 الشعبة: {classroom.name}")
        print("=" * 60)
        
        for student in students:
            status_key = f'status_{student.id}'
            status = request.POST.get(status_key)
            notes = request.POST.get(f'notes_{student.id}', '')
            
            # تحقق من القيمة المرسلة
            if status is None:
                status = 'present'  # الافتراضي
                print(f"   ⚠️  {student.full_name}: لم ترسل قيمة، استخدام الافتراضي (حاضر)")
            else:
                print(f"   ✅ {student.full_name}: {status}")
            
            if status == 'present':
                present_count += 1
            
            try:
                attendance = Attendance.objects.create(
                    student=student,
                    classroom=classroom,
                    date=date_obj,
                    status=status,
                    notes=notes
                )
                success_count += 1
            except IntegrityError as e:
                error_messages.append(f'خطأ في تسجيل حضور الطالب {student.full_name}: {str(e)}')
        
        absent_count = success_count - present_count
        print("=" * 60)
        print(f"📊 النتائج النهائية:")
        print(f"   ✅ تم تسجيل: {success_count} طالب")
        print(f"   👥 الحاضرون: {present_count}")
        print(f"   ❌ الغائبون: {absent_count}")
        print("=" * 60)
        
        if success_count > 0:
            messages.success(request, f'تم تسجيل حضور {success_count} طالب بنجاح: {present_count} حاضر و {absent_count} غائب')
        
        if error_messages:
            messages.error(request, '<br>'.join(error_messages))
        
        return redirect('attendance:attendance')


class AttendanceToolsView(LoginRequiredMixin, View):
    template_name = 'attendance/attendance_tools.html'

    def get(self, request):
        if not request.user.is_superuser:
            return HttpResponseForbidden('غير مصرح')
        context = {
            'students': Student.objects.order_by('full_name'),
            'classrooms': Classroom.objects.filter(is_active=True).order_by('name'),
            'status_choices': Attendance.Status.choices,
            'today': timezone.now().date(),
        }
        return render(request, self.template_name, context)

    def post(self, request):
        if not request.user.is_superuser:
            return HttpResponseForbidden('غير مصرح')
        action = request.POST.get('action')
        if action == 'fix_notifications':
            self._handle_fix_notifications(request)
        elif action == 'update_attendance':
            self._handle_update_attendance(request)
        return redirect('attendance:attendance_tools')

    def _handle_fix_notifications(self, request):
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        student_id = request.POST.get('student_id')
        create_missing = request.POST.get('create_missing') == '1'

        try:
            from_date = datetime.strptime(from_date, '%Y-%m-%d').date()
            to_date = datetime.strptime(to_date, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            messages.error(request, 'يرجى إدخال تاريخ صحيح.')
            return

        if from_date > to_date:
            messages.error(request, 'تاريخ البداية يجب أن يكون قبل تاريخ النهاية.')
            return

        attendances = Attendance.objects.filter(date__range=(from_date, to_date))
        if student_id and str(student_id).isdigit():
            attendances = attendances.filter(student_id=int(student_id))

        updated = 0
        created = 0
        missing = 0
        for att in attendances.select_related('student', 'classroom'):
            u, c, m = self._sync_notification(att, create_missing=create_missing)
            updated += u
            created += c
            missing += m

        messages.success(
            request,
            f'تم تحديث {updated} إشعار، إنشاء {created} إشعار، وتعذر تحديث {missing} إشعار.',
        )

    def _handle_update_attendance(self, request):
        student_id = request.POST.get('edit_student_id')
        classroom_id = request.POST.get('edit_classroom_id')
        status = request.POST.get('edit_status')
        date_str = request.POST.get('edit_date')
        notes = request.POST.get('edit_notes', '').strip()
        sync_notification = request.POST.get('sync_notification') == '1'
        create_missing = request.POST.get('sync_create_missing') == '1'

        if not (student_id and classroom_id and status and date_str):
            messages.error(request, 'يرجى تعبئة جميع الحقول المطلوبة.')
            return

        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            messages.error(request, 'تاريخ غير صالح.')
            return

        student = Student.objects.filter(id=student_id).first()
        classroom = Classroom.objects.filter(id=classroom_id).first()
        if not student or not classroom:
            messages.error(request, 'الطالب أو الشعبة غير صحيحة.')
            return

        attendance, created = Attendance.objects.update_or_create(
            student=student,
            date=date_obj,
            defaults={
                'classroom': classroom,
                'status': status,
                'notes': notes,
            },
        )

        if sync_notification:
            self._sync_notification(attendance, create_missing=create_missing)

        if created:
            messages.success(request, 'تم إنشاء سجل الحضور بنجاح.')
        else:
            messages.success(request, 'تم تحديث سجل الحضور بنجاح.')

    def _sync_notification(self, attendance, create_missing=False):
        title, message = build_attendance_notification(attendance)
        qs = MobileNotification.objects.filter(
            notification_type='attendance',
            student=attendance.student,
            created_at__date=attendance.date,
        )
        if qs.exists():
            updated = qs.update(title=title, message=message)
            return updated, 0, 0
        if create_missing:
            MobileNotification.objects.create(
                student=attendance.student,
                teacher=None,
                notification_type='attendance',
                title=title,
                message=message,
            )
            return 0, 1, 0
        return 0, 0, 1
