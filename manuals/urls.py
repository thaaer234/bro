from django.urls import path

from . import views


app_name = "manuals"


urlpatterns = [
    path("", views.ManualsHomeView.as_view(), name="home"),
    path("handbook/", views.ManualsHandbookView.as_view(), name="handbook"),
    path("user/", views.ManualsUserGuideSelectView.as_view(), name="user_select"),
    path("user/handbook/", views.ManualsUserHandbookView.as_view(), name="user_handbook"),
    path("user/handbook/print/", views.ManualsUserHandbookPrintView.as_view(), name="user_handbook_print"),
    path("markdown/", views.ManualsMarkdownDownloadView.as_view(), name="markdown"),
]
