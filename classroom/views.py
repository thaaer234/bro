from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import View, TemplateView, ListView, CreateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from .models import Classroom ,Classroomenrollment ,ClassroomSubject
from .form import ClassroomForm ,ClassroomSubjectForm
from students.models import Student
from accounts.models import Studentenrollment
from courses.models import Subject
from django.db import IntegrityError
from django.core.exceptions import ValidationError
import pandas as pd
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
import openpyxl
from openpyxl.styles import Font, Alignment
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count
from django.template.loader import render_to_string
from django.contrib.staticfiles import finders
from django.conf import settings
from employ.models import Teacher
from xhtml2pdf import pisa
try:
    from weasyprint import HTML
    from weasyprint.urls import default_url_fetcher
    WEASYPRINT_AVAILABLE = True
except Exception:
    HTML = None
    default_url_fetcher = None
    WEASYPRINT_AVAILABLE = False
import os
import tempfile
import io
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily




# Create your views here.
class ClassroomListView(ListView):
    template_name = 'classroom/classroom.html'
    model = Classroom
    context_object_name = 'classrooms'
    
    
class CreateClassroomView(CreateView):
    model = Classroom
    form_class = ClassroomForm
    template_name = 'classroom/create_classroom.html'
    success_url = reverse_lazy('classroom:classroom')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم إضافة الشعبة بنجاح')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'حدث خطأ في إدخال البيانات')
        return super().form_invalid(form)    
    

class AssignStudentsView(View):
    template_name = 'classroom/assign_students.html'

    def get(self, request, classroom_id):
        classroom = get_object_or_404(Classroom, id=classroom_id)
        
        # الحصول على الطلاب المسجلين في هذه الشعبة
        current_enrollments = Classroomenrollment.objects.filter(classroom=classroom)
        assigned_students = Student.objects.filter(
            classroom_enrollments__classroom=classroom
        ).distinct()
        
        # نبدأ بكل الطلاب النشطين فقط
        base_students = Student.objects.filter(is_active=True)

        if classroom.class_type == 'study':
            # للشعبة الدراسية: نعرض فقط الطلاب غير مسجلين في أي شعبة دراسية ومن نفس الفرع
            enrolled_in_study = Classroomenrollment.objects.filter(
                classroom__class_type='study'
            ).values_list('student__id', flat=True)
            
            available_students = base_students.exclude(
                id__in=enrolled_in_study
            ).distinct()
        else:
            # للدورة: نعرض جميع الطلاب غير مسجلين في هذه الدورة
            enrolled_in_course = current_enrollments.values_list('student__id', flat=True)
            available_students = base_students.exclude(id__in=enrolled_in_course).distinct()
        
        return render(request, self.template_name, {
            'classroom': classroom,
            'unassigned_students': available_students,
            'assigned_students': assigned_students
        })

    def post(self, request, classroom_id):
        classroom = get_object_or_404(Classroom, id=classroom_id)
        student_ids = request.POST.getlist('student_ids')

        if not student_ids:
            messages.warning(request, 'يرجى اختيار طالب واحد على الأقل.')
            return redirect('classroom:assign_students', classroom_id=classroom_id)

        added_count = 0
        for student_id in student_ids:
            student = get_object_or_404(Student, id=student_id)
                
            try:
                enrollment = Classroomenrollment(
                    student=student,
                    classroom=classroom,
                )
                enrollment.full_clean()
                enrollment.save()
                added_count += 1
            except ValidationError as e:
                messages.error(request, f'{student.full_name}: {" | ".join(e.messages)}')
                continue
            except IntegrityError:
                messages.warning(request, f'الطالب {student.full_name} مسجل بالفعل في هذه الشعبة')
                continue

        if added_count:
            messages.success(request, f'تمت إضافة {added_count} طالب إلى الشعبة بنجاح')
        
        return redirect('classroom:assign_students', classroom_id=classroom_id)

class UnassignStudentView(View):
    def post(self, request, classroom_id, student_id):
        enrollment = get_object_or_404(
            Classroomenrollment,
            classroom_id=classroom_id,
            student_id=student_id
        )
        enrollment.delete()
        messages.success(request, 'تم إزالة الطالب من الشعبة بنجاح')
        return redirect('classroom:assign_students', classroom_id=classroom_id)

class ClassroomStudentsView(ListView):
    template_name = 'classroom/classroom_students.html'
    context_object_name = 'students'

    def get_queryset(self):
        classroom = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        base_qs = Student.objects.filter(
            classroom_enrollments__classroom=classroom
        )
        if classroom.class_type == 'study':
            # للشعبة الدراسية: نراعي الفرع
            return base_qs.distinct().order_by('full_name')
        else:
            # للدورة: نعرض جميع الطلاب المسجلين بغض النظر عن الفرع
            return base_qs.distinct().order_by('full_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        context['classroom'] = classroom
        return context


def _prepare_classroom_cards(classrooms):
    for classroom in classrooms:
        try:
            classroom.branch_display = classroom.get_branches_display()
        except Exception:
            classroom.branch_display = getattr(classroom, 'branches', '') or ''


def _classroom_cards_pdf_link_callback(uri, rel):
    if uri.startswith('http://') or uri.startswith('https://'):
        return uri

    if uri.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
    elif uri.startswith(settings.STATIC_URL):
        path = finders.find(uri.replace(settings.STATIC_URL, ''))
    else:
        path = finders.find(uri)

    if not path:
        return uri

    if isinstance(path, (list, tuple)):
        path = path[0]
    return path


def _register_pdf_fonts():
    try:
        font_regular = finders.find('font/Cairo-400.ttf')
        font_bold = finders.find('font/Cairo-600.ttf') or font_regular
        font_black = finders.find('font/Cairo-800.ttf') or font_bold or font_regular

        if font_regular:
            pdfmetrics.registerFont(TTFont('Cairo', font_regular))
        if font_bold and font_bold != font_regular:
            pdfmetrics.registerFont(TTFont('Cairo-Bold', font_bold))
        if font_black and font_black not in (font_regular, font_bold):
            pdfmetrics.registerFont(TTFont('Cairo-Black', font_black))

        if font_regular:
            registerFontFamily(
                'Cairo',
                normal='Cairo',
                bold='Cairo-Bold' if font_bold else 'Cairo',
                italic='Cairo',
                boldItalic='Cairo-Bold' if font_bold else 'Cairo',
            )
    except Exception:
        pass


def _classroom_weasyprint_url_fetcher(url):
    if not default_url_fetcher:
        return None

    if url.startswith(settings.STATIC_URL):
        path = finders.find(url.replace(settings.STATIC_URL, ''))
    elif url.startswith(settings.MEDIA_URL):
        path = os.path.join(settings.MEDIA_ROOT, url.replace(settings.MEDIA_URL, ''))
    else:
        return default_url_fetcher(url)

    if not path:
        return default_url_fetcher(url)

    if isinstance(path, (list, tuple)):
        path = path[0]

    return default_url_fetcher(f'file://{path}')


def _inline_css_vars(html):
    css_vars = {
        'ink': '#0e1424',
        'muted': '#9fa6b6',
        'paper': '#ffffff',
        'line': '#d8e0ef',
        'purple': '#513996',
        'purple-dark': '#4f2f86',
        'purple-light': '#6b4aa7',
        'gold': '#f0a22b',
        'teal': '#0b6c8e',
        'grid': 'rgba(255, 255, 255, 0.08)',
        'card-width': '100mm',
        'card-height': '60mm',
    }

    for key, value in css_vars.items():
        html = html.replace(f'var(--{key})', value)
    return html


class ClassroomCardsPrintView(LoginRequiredMixin, TemplateView):
    template_name = 'classroom/classroom_cards_print.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        should_generate = self.request.GET.get('generate') == '1'
        classrooms = []
        teachers_total = 0

        if should_generate:
            classrooms = list(
                Classroom.objects.all()
                .order_by('name')
                .annotate(students_count=Count('enrollments__student', distinct=True))
            )
            teachers_total = Teacher.objects.count()

        _prepare_classroom_cards(classrooms)

        cards = []
        if should_generate:
            for classroom in classrooms:
                subtitle = classroom.branch_display if classroom.class_type == 'study' else ''
                cards.append({
                    'title': classroom.name,
                    'subtitle': subtitle,
                    'count': classroom.students_count,
                    'count_label': 'عدد الطلاب',
                    'kicker': 'بطاقة شعبة',
                    'is_teachers': False,
                })

            cards.append({
                'title': 'المدرسون',
                'subtitle': '',
                'count': teachers_total,
                'count_label': 'عدد المدرسين',
                'kicker': 'بطاقة المعهد',
                'is_teachers': True,
            })

        per_page = 8
        pages = [cards[i:i + per_page] for i in range(0, len(cards), per_page)]
        if should_generate and not pages:
            pages = [[]]

        context.update({
            'should_generate': should_generate,
            'pages': pages,
            'cards_total': len(cards),
            'classrooms_total': len(classrooms),
            'teachers_total': teachers_total,
            'pdf': False,
        })
        return context


def classroom_cards_print_pdf(request):
    should_generate = request.GET.get('generate') == '1'
    classrooms = []
    teachers_total = 0

    if should_generate:
        classrooms = list(
            Classroom.objects.all()
            .order_by('name')
            .annotate(students_count=Count('enrollments__student', distinct=True))
        )
        teachers_total = Teacher.objects.count()

    _prepare_classroom_cards(classrooms)

    cards = []
    if should_generate:
        for classroom in classrooms:
            subtitle = classroom.branch_display if classroom.class_type == 'study' else ''
            cards.append({
                'title': classroom.name,
                'subtitle': subtitle,
                'count': classroom.students_count,
                'count_label': 'عدد الطلاب',
                'kicker': 'بطاقة شعبة',
                'is_teachers': False,
            })

        cards.append({
            'title': 'المدرسون',
            'subtitle': '',
            'count': teachers_total,
            'count_label': 'عدد المدرسين',
            'kicker': 'بطاقة المعهد',
            'is_teachers': True,
        })

    per_page = 8
    pages = [cards[i:i + per_page] for i in range(0, len(cards), per_page)]
    if should_generate and not pages:
        pages = [[]]

    context = {
        'should_generate': should_generate,
        'pages': pages,
        'cards_total': len(cards),
        'classrooms_total': len(classrooms),
        'teachers_total': teachers_total,
        'pdf': True,
    }

    html = render_to_string('classroom/classroom_cards_print.html', context, request=request)
    tmp_dir = os.path.join(settings.BASE_DIR, '_tmp_pdf')
    os.makedirs(tmp_dir, exist_ok=True)
    os.environ['TMP'] = tmp_dir
    os.environ['TEMP'] = tmp_dir
    tempfile.tempdir = tmp_dir

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename=\"classroom_cards.pdf\"'

    if WEASYPRINT_AVAILABLE:
        pdf_bytes = HTML(
            string=html,
            base_url=request.build_absolute_uri('/'),
            url_fetcher=_classroom_weasyprint_url_fetcher,
        ).write_pdf()
        response.write(pdf_bytes)
        return response

    _register_pdf_fonts()
    html = _inline_css_vars(html)
    pisa.CreatePDF(html, dest=response, link_callback=_classroom_cards_pdf_link_callback, encoding='UTF-8')
    return response

class DeleteClassroomView(DeleteView):
    model = Classroom
    pk_url_kwarg = 'classroom_id'
    success_url = reverse_lazy('classroom:classroom')
    template_name = 'classroom/classroom_confirm_delete.html'

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'تم حذف الشعبة بنجاح')
        return super().delete(request, *args, **kwargs)


class ClassroomSubjectListView(ListView):
    model = ClassroomSubject
    template_name = 'classroom/classroom_subject_list.html'

    def get_queryset(self):
        return ClassroomSubject.objects.filter(
            classroom_id=self.kwargs['classroom_id']
        ).select_related('subject').prefetch_related('subject__teachers')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['classroom'] = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        return context

class ClassroomSubjectCreateView(CreateView):
    model = ClassroomSubject
    form_class = ClassroomSubjectForm
    template_name = 'classroom/classroom_subject_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        classroom = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        kwargs['classroom'] = classroom
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial['classroom'] = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        return initial

    # في ClassroomSubjectCreateView، قم بتعديل طريقة get_context_data
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        classroom = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        context['classroom'] = classroom
        
        # تحميل المواد مع معلميها مسبقاً لتحسين الأداء
        if classroom.class_type == 'study':
            if classroom.branches == 'علمي':
                subjects = Subject.objects.filter(
                    subject_type__in=['scientific', 'common']
                ).prefetch_related('teachers')
            elif classroom.branches == 'أدبي':
                subjects = Subject.objects.filter(
                    subject_type__in=['literary', 'common']
                ).prefetch_related('teachers')
            elif classroom.branches == 'تاسع':
                subjects = Subject.objects.filter(
                    subject_type__in=['ninth', 'common']
                ).prefetch_related('teachers')
            else:
                subjects = Subject.objects.none()
        else:
            subjects = Subject.objects.all().prefetch_related('teachers')
        
        # إنشاء قائمة بالمواد مع أسماء المعلمين
        subject_choices = []
        for subject in subjects:
            teacher_names = ", ".join([teacher.full_name for teacher in subject.teachers.all()])
            if teacher_names:
                display_name = f"{subject.name} ({teacher_names})"
            else:
                display_name = subject.name
            subject_choices.append((subject.id, display_name))
        
        context['subject_choices'] = subject_choices
        return context

    def form_valid(self, form):
        form.instance.classroom = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('classroom:classroom_subject_list', kwargs={'classroom_id': self.kwargs['classroom_id']})


class AssignToCourseView(View):
    template_name = 'classroom/assign_to_course.html'

    def get(self, request, course_id):
        course = get_object_or_404(Classroom, id=course_id, class_type='course')
        enrollments = Classroomenrollment.objects.filter(classroom=course)
        
        enrolled_student_ids = enrollments.values_list('student__id', flat=True)
        available_students = Student.objects.exclude(id__in=enrolled_student_ids)
        
        return render(request, self.template_name, {
            'course': course,
            'available_students': available_students,
            'enrolled_students': [e.student for e in enrollments]
        })

    def post(self, request, course_id):
        course = get_object_or_404(Classroom, id=course_id, class_type='course')
        student_ids = request.POST.getlist('student_ids')

        if student_ids:
            for student_id in student_ids:
                Classroomenrollment.objects.get_or_create(
                    student_id=student_id,
                    classroom=course,
                    
                )
            messages.success(request, 'تم تسجيل الطلاب في الدورة بنجاح')
        
        return redirect('classroom:assign_to_course', course_id=course_id)
    
    
    
    


def export_classroom_students_to_excel(request, classroom_id):
    # جلب بيانات الشعبة
    classroom = get_object_or_404(Classroom, id=classroom_id)
    
    # جلب طلاب الشعبة فقط
    students = Student.objects.filter(
        classroom_enrollments__classroom=classroom
    ).values('full_name')
    
    # تحويل البيانات إلى DataFrame
    df = pd.DataFrame(list(students))
    
    # إضافة عمود الأرقام التسلسلية
    df.insert(0, '#', range(1, len(df) + 1))
    
    # إعادة تسمية الأعمدة بالعربية
    df.rename(columns={'full_name': 'اسم الطالب'}, inplace=True)
    
    # إعداد اسم الملف والاستجابة
    filename = f"طلاب_{classroom.name}.xlsx"
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # إنشاء Excel باستخدام pandas
    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(
            writer, 
            sheet_name='الطلاب', 
            index=False,
            startrow=0
        )
        
        # الحصول على ورقة العمل وتنسيقها
        worksheet = writer.sheets['الطلاب']
        
        # تنسيق الأعمدة (ضبط العرض)
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width
        
        # تنسيق الرأس (جعل الخط عريض ومركز)
        for cell in worksheet[1]:
            cell.font = Font(bold=True)
            cell.alignment = Alignment(horizontal='center', vertical='center')
    
    return response



from django.views.generic import UpdateView

# ثم أضف الصف الخاص بالتعديل
class UpdateClassroomView(UpdateView):
    model = Classroom
    form_class = ClassroomForm
    template_name = 'classroom/update_classroom.html'
    pk_url_kwarg = 'classroom_id'
    
    def get_success_url(self):
        return reverse_lazy('classroom:classroom')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم تعديل الشعبة بنجاح')
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'حدث خطأ في تعديل البيانات')
        return super().form_invalid(form)
    
# classroom/views.py
from django.views.generic import UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages

class ClassroomSubjectUpdateView(UpdateView):
    model = ClassroomSubject
    form_class = ClassroomSubjectForm
    template_name = 'classroom/classroom_subject_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        classroom = get_object_or_404(Classroom, id=self.kwargs['classroom_id'])
        kwargs['classroom'] = classroom
        return kwargs

    def get_success_url(self):
        return reverse('classroom:classroom_subject_list', kwargs={'classroom_id': self.kwargs['classroom_id']})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'تم تعديل المادة في الشعبة بنجاح')
        return response

class ClassroomSubjectDeleteView(DeleteView):
    model = ClassroomSubject
    template_name = 'classroom/classroom_subject_confirm_delete.html'
    
    def get_success_url(self):
        return reverse('classroom:classroom_subject_list', kwargs={'classroom_id': self.kwargs['classroom_id']})

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'تم حذف المادة من الشعبة بنجاح')
        return super().delete(request, *args, **kwargs)
