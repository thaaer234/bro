from django.urls import path

from . import views

app_name = "academic_years"

urlpatterns = [
    path("select/", views.AcademicYearSelectView.as_view(), name="select_current"),
    path("unlock/<int:pk>/", views.AcademicYearUnlockView.as_view(), name="unlock"),
    path("manage/<int:pk>/", views.AcademicYearManageView.as_view(), name="manage"),
    path("activate/<int:pk>/", views.AcademicYearActivateView.as_view(), name="activate"),
    
    # نقل الدورات
    path("transfers/", views.AcademicYearTransferBatchListView.as_view(), name="transfer_list"),
    path("transfers/create/", views.AcademicYearTransferBatchCreateView.as_view(), name="transfer_create"),
    path("transfers/<int:pk>/", views.AcademicYearTransferBatchDetailView.as_view(), name="transfer_detail"),
    path("transfers/<int:pk>/execute/", views.AcademicYearTransferBatchExecuteView.as_view(), name="transfer_execute"),
    path("transfers/recognize-entries/", views.JournalEntryRecognitionView.as_view(), name="recognize_entries"),
    path("transfers/recognize-accounts/", views.AccountRecognitionView.as_view(), name="recognize_accounts"),
    
    # نقل القيود بدون فصول
    path("journal-entries-transfer/", views.JournalEntryTransferBatchListView.as_view(), name="journal_entry_transfer_list"),
    path("journal-entries-transfer/create/", views.JournalEntryTransferBatchCreateView.as_view(), name="journal_entry_transfer_create"),
    path("journal-entries-transfer/<int:pk>/", views.JournalEntryTransferBatchDetailView.as_view(), name="journal_entry_transfer_detail"),
    path("journal-entries-transfer/<int:pk>/execute/", views.JournalEntryTransferBatchExecuteView.as_view(), name="journal_entry_transfer_execute"),
]
