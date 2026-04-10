from django.urls import path
from employ.decorators import require_superuser

from . import views


app_name = "manuals"


urlpatterns = [
    path("", require_superuser(views.ManualsHomeView.as_view()), name="home"),
    path("handbook/", require_superuser(views.ManualsHandbookView.as_view()), name="handbook"),
    path("user/", require_superuser(views.ManualsUserGuideSelectView.as_view()), name="user_select"),
    path("user/handbook/", require_superuser(views.ManualsUserHandbookView.as_view()), name="user_handbook"),
    path("user/handbook/print/", require_superuser(views.ManualsUserHandbookPrintView.as_view()), name="user_handbook_print"),
    path("markdown/", require_superuser(views.ManualsMarkdownDownloadView.as_view()), name="markdown"),
]
