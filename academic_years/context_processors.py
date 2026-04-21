from academic_years.services.session import get_current_academic_year, get_or_create_access_policy


def academic_year_context(request):
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    academic_year = getattr(request, "current_academic_year", None)
    if academic_year is None:
        academic_year = get_current_academic_year(request)

    if not academic_year:
        return {
            "current_academic_year": None,
            "current_academic_year_policy": None,
        }

    return {
        "current_academic_year": academic_year,
        "current_academic_year_policy": get_or_create_access_policy(academic_year),
    }

