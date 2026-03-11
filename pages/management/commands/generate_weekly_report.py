from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from pages.models import ReportSchedule
from pages.reporting import create_system_report


class Command(BaseCommand):
    help = "Generate the weekly system report when the schedule is due."

    def handle(self, *args, **options):
        schedule = ReportSchedule.get_solo()
        if not schedule.is_enabled:
            self.stdout.write("Weekly report schedule is disabled.")
            return

        now = timezone.now()
        if not schedule.next_run:
            schedule.next_run = schedule.compute_next_run()
            schedule.save()

        if schedule.next_run and schedule.next_run > now:
            self.stdout.write(f"Next scheduled run: {schedule.next_run}")
            return

        period_end = timezone.localdate()
        period_start = period_end - timedelta(days=6)

        report = create_system_report(
            period_start=period_start,
            period_end=period_end,
            report_type="scheduled",
        )

        schedule.last_run = now
        schedule.next_run = schedule.compute_next_run(now + timedelta(seconds=1))
        schedule.save()

        self.stdout.write(f"Created report #{report.pk}")
