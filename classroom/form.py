from django import forms
from courses.models import Subject
from .models import Classroom ,ClassroomSubject

class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'class_type': forms.Select(attrs={'class': 'form-control'}),
            'branches': forms.Select(attrs={'class': 'form-control'}),
            'min_capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'max_capacity': forms.NumberInput(attrs={'class': 'form-control'}),
            'course': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.instance.class_type == 'course':
            self.fields['branches'].widget = forms.HiddenInput()

        # Filter the course field to active and scoped academic year
        if 'course' in self.fields:
            from accounts.models import Course
            from academic_years.middleware import get_current_academic_year_thread
            current_ay = get_current_academic_year_thread()
            
            # Start with only active courses
            course_qs = Course.objects.filter(is_active=True)
            
            # Scope to current academic year if available
            if current_ay:
                course_qs = course_qs.filter(academic_year=current_ay)
            
            # Ensure the currently linked course is in the queryset
            if self.instance and self.instance.pk and self.instance.course:
                current_course_pk = self.instance.course.pk
                from django.db.models import Q
                course_qs = Course.objects.filter(Q(id=current_course_pk) | Q(id__in=course_qs.values_list('id', flat=True)))
                
            self.fields['course'].queryset = course_qs.distinct()

        # Hide is_visible if the user is not a superuser
        if user and not user.is_superuser:
            if 'is_visible' in self.fields:
                self.fields['is_visible'].widget = forms.HiddenInput()
        
        
class ClassroomSubjectForm(forms.ModelForm):
    class Meta:
        model = ClassroomSubject
        fields = ['classroom', 'subject']
        widgets = {
            'classroom': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        classroom = kwargs.pop('classroom', None)
        super().__init__(*args, **kwargs)
        
        if classroom:
            # تصفية المواد بناءً على نوع الشعبة وفرعها
            if classroom.class_type == 'study':
                if classroom.branches == 'علمي':
                    # للمواد العلمية والمشتركة
                    self.fields['subject'].queryset = Subject.objects.filter(
                        subject_type__in=['scientific', 'common']
                    )
                elif classroom.branches == 'أدبي':
                    # للمواد الأدبية والمشتركة
                    self.fields['subject'].queryset = Subject.objects.filter(
                        subject_type__in=['literary', 'common']
                    )
                elif classroom.branches == 'تاسع':
                    # للمواد الخاصة بالتاسع والمشتركة
                    self.fields['subject'].queryset = Subject.objects.filter(
                        subject_type__in=['ninth', 'common']
                    )
            else:
                # للدورات: عرض جميع المواد
                self.fields['subject'].queryset = Subject.objects.all()          