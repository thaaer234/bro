from datetime import date
from types import SimpleNamespace

from django.test import SimpleTestCase

from .forms import QuickSessionAttendanceBulkForm


class QuickSessionAttendanceBulkFormTests(SimpleTestCase):
    def _session(self):
        return SimpleNamespace(
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 5),
            course_id=10,
        )

    def _enrollment(self, enrollment_id=1, course_id=10):
        return SimpleNamespace(
            id=enrollment_id,
            course_id=course_id,
            student=SimpleNamespace(full_name="Test Student"),
        )

    def test_rejects_attendance_date_outside_session_range(self):
        enrollment = self._enrollment()
        form = QuickSessionAttendanceBulkForm(
            {
                "attendance_date": "2026-05-06",
                "student_1_status": "present",
                "student_1_notes": "",
            },
            session=self._session(),
            enrollments=[enrollment],
        )

        self.assertFalse(form.is_valid())
        self.assertIn("attendance_date", form.errors)

    def test_rejects_enrollment_from_different_course(self):
        enrollment = self._enrollment(course_id=99)
        form = QuickSessionAttendanceBulkForm(
            {
                "attendance_date": "2026-05-03",
                "student_1_status": "present",
                "student_1_notes": "",
            },
            session=self._session(),
            enrollments=[enrollment],
        )

        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
