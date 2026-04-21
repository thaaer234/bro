from django.urls import path

from . import views

app_name = "academic_years"

urlpatterns = [
    path("select/", views.AcademicYearSelectView.as_view(), name="select_current"),
    path("unlock/<int:pk>/", views.AcademicYearUnlockView.as_view(), name="unlock"),
    path("manage/<int:pk>/", views.AcademicYearManageView.as_view(), name="manage"),
    path("activate/<int:pk>/", views.AcademicYearActivateView.as_view(), name="activate"),
    path("transfers/", views.AcademicYearTransferBatchListView.as_view(), name="transfer_list"),
    path("transfers/create/", views.AcademicYearTransferBatchCreateView.as_view(), name="transfer_create"),
    path("transfers/<int:pk>/", views.AcademicYearTransferBatchDetailView.as_view(), name="transfer_detail"),
    path("transfers/<int:pk>/execute/", views.AcademicYearTransferBatchExecuteView.as_view(), name="transfer_execute"),
]
