from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
import os
import gzip
from io import BytesIO


def secure_backup(request):
    key = request.GET.get("key")

    if key != settings.BACKUP_KEY:
        return HttpResponseForbidden("Forbidden")

    db_path = settings.BASE_DIR / "db.sqlite3"

    if not os.path.exists(db_path):
        return HttpResponseForbidden("Database not found")

    buffer = BytesIO()
    with open(db_path, "rb") as f:
        with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
            gz.write(f.read())

    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/gzip"
    )
    response["Content-Disposition"] = 'attachment; filename="db.sqlite3.gz"'
    return response
