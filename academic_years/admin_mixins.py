from django.contrib import admin
from django.db.models import Q

from academic_years.services.session import get_current_academic_year
from quick.models import AcademicYear


def scope_queryset_to_current_academic_year(queryset, request, field_name="academic_year", include_null=False):
    academic_year = get_current_academic_year(request)
    if not academic_year or not field_name:
        return queryset

    year_filter = Q(**{field_name: academic_year})
    if include_null:
        year_filter |= Q(**{f"{field_name}__isnull": True})
    return queryset.filter(year_filter)


class AcademicYearScopedAdminMixin(admin.ModelAdmin):
    academic_year_field = "academic_year"
    include_null_academic_year = False
    academic_year_foreignkey_scopes = {}
    academic_year_manytomany_scopes = {}
    lock_academic_year_field = True

    def get_current_academic_year(self, request):
        return get_current_academic_year(request)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return scope_queryset_to_current_academic_year(
            queryset,
            request,
            field_name=self.academic_year_field,
            include_null=self.include_null_academic_year,
        )

    def save_model(self, request, obj, form, change):
        academic_year = self.get_current_academic_year(request)
        if (
            academic_year
            and hasattr(obj, "academic_year_id")
            and not obj.academic_year_id
        ):
            obj.academic_year = academic_year
        super().save_model(request, obj, form, change)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        academic_year = self.get_current_academic_year(request)
        scope_field = self.academic_year_foreignkey_scopes.get(db_field.name)

        if scope_field:
            base_queryset = kwargs.get("queryset") or db_field.remote_field.model._default_manager.all()
            kwargs["queryset"] = scope_queryset_to_current_academic_year(
                base_queryset,
                request,
                field_name=scope_field,
            )
        elif db_field.name == "academic_year" and academic_year and self.lock_academic_year_field:
            kwargs["queryset"] = AcademicYear.objects.filter(pk=academic_year.pk)

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        scope_field = self.academic_year_manytomany_scopes.get(db_field.name)
        if scope_field:
            base_queryset = kwargs.get("queryset") or db_field.remote_field.model._default_manager.all()
            kwargs["queryset"] = scope_queryset_to_current_academic_year(
                base_queryset,
                request,
                field_name=scope_field,
            )
        return super().formfield_for_manytomany(db_field, request, **kwargs)
