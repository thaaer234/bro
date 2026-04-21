from typing import Optional

from quick.models import AcademicYear

from academic_years.models import AcademicYearAccess, AcademicYearSystemState


CURRENT_ACADEMIC_YEAR_SESSION_KEY = "current_academic_year_id"
UNLOCKED_ACADEMIC_YEARS_SESSION_KEY = "unlocked_academic_year_ids"


def get_or_create_access_policy(academic_year: AcademicYear) -> AcademicYearAccess:
    policy, _ = AcademicYearAccess.objects.get_or_create(academic_year=academic_year)
    return policy


def get_active_system_academic_year() -> Optional[AcademicYear]:
    state = AcademicYearSystemState.load()
    return state.active_academic_year if state else None


def get_available_academic_years():
    academic_years = list(AcademicYear.objects.order_by("-start_date", "-id"))
    available_years = []
    for academic_year in academic_years:
        policy = get_or_create_access_policy(academic_year)
        if policy.is_archived:
            continue
        available_years.append(academic_year)
    return available_years


def academic_year_requires_unlock(academic_year: AcademicYear) -> bool:
    policy = get_or_create_access_policy(academic_year)
    return academic_year.is_closed or policy.requires_password


def get_current_academic_year(request) -> Optional[AcademicYear]:
    academic_year_id = request.session.get(CURRENT_ACADEMIC_YEAR_SESSION_KEY)
    if academic_year_id:
        academic_year = AcademicYear.objects.filter(pk=academic_year_id).first()
        if academic_year and not get_or_create_access_policy(academic_year).is_archived:
            return academic_year
    system_academic_year = get_active_system_academic_year()
    if system_academic_year and not get_or_create_access_policy(system_academic_year).is_archived:
        return system_academic_year
    return None


def get_auto_selected_academic_year(request) -> Optional[AcademicYear]:
    return None


def set_current_academic_year(request, academic_year: AcademicYear):
    request.session[CURRENT_ACADEMIC_YEAR_SESSION_KEY] = academic_year.pk


def clear_current_academic_year(request):
    request.session.pop(CURRENT_ACADEMIC_YEAR_SESSION_KEY, None)


def get_unlocked_academic_year_ids(request):
    return set(request.session.get(UNLOCKED_ACADEMIC_YEARS_SESSION_KEY, []))


def unlock_academic_year(request, academic_year: AcademicYear):
    unlocked_ids = get_unlocked_academic_year_ids(request)
    unlocked_ids.add(academic_year.pk)
    request.session[UNLOCKED_ACADEMIC_YEARS_SESSION_KEY] = sorted(unlocked_ids)


def lock_academic_year(request, academic_year: AcademicYear):
    unlocked_ids = get_unlocked_academic_year_ids(request)
    if academic_year.pk in unlocked_ids:
        unlocked_ids.remove(academic_year.pk)
        request.session[UNLOCKED_ACADEMIC_YEARS_SESSION_KEY] = sorted(unlocked_ids)
