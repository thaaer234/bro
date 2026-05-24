from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from academic_years.services.session import (
    academic_year_requires_unlock,
    get_current_academic_year,
    get_or_create_access_policy,
    get_unlocked_academic_year_ids,
)


import threading

_thread_local = threading.local()

def get_current_academic_year_thread():
    return getattr(_thread_local, 'current_academic_year', None)


class AcademicYearAccessMiddleware:
    EXEMPT_PATH_PREFIXES = (
        "/login/",
        "/logout/",
        "/admin/",
        "/sham/thaaer7426/",
        "/static/",
        "/media/",
        "/academic-years/select/",
        "/academic-years/unlock/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return self.get_response(request)

        request.current_academic_year = get_current_academic_year(request)

        # Store in thread-local for models and templates automatic isolation
        _thread_local.current_academic_year = request.current_academic_year

        try:
            if request.path.startswith(self.EXEMPT_PATH_PREFIXES):
                return self.get_response(request)

            academic_year = request.current_academic_year
            if not academic_year:
                return redirect(reverse("academic_years:select_current"))

            policy = get_or_create_access_policy(academic_year)
            if academic_year_requires_unlock(academic_year):
                unlocked_ids = get_unlocked_academic_year_ids(request)
                if academic_year.pk not in unlocked_ids:
                    return redirect(reverse("academic_years:unlock", kwargs={"pk": academic_year.pk}))

            if (
                policy.is_read_only
                and request.method in {"POST", "PUT", "PATCH", "DELETE"}
                and not request.user.is_superuser
            ):
                return HttpResponseForbidden("الفصل الحالي في وضع القراءة فقط.")

            return self.get_response(request)
        finally:
            # Clean up after request ends to prevent memory leak and cross-request contamination
            if hasattr(_thread_local, 'current_academic_year'):
                del _thread_local.current_academic_year
