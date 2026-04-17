from django.urls import path

from .views import index

app_name = "sitemap"

urlpatterns = [
    path("", index, name="sitemap_index"),
]
