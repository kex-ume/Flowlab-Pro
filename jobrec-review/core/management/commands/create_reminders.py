from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from core.models import EnvironmentReminder, Location, Notification, Primary
from core.auth_utils import get_users_with_perm
from core.notifications import personnel_users, send_overdue_job_reminders
from core.ei_workflow import evaluate_clocks


class Command(BaseCommand):
    help = ('Creates environment reminders for today (one per lab/location) and '
            'primary recalibration reminders (90 days in advance). Notifies all '
            'personnel when a reminder slot is created, and nudges them again '
            'once a slot time has passed while still unrecorded.')

    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.localtime()
        created = 0
        created += send_overdue_job_reminders()
        evaluate_clocks()

        # Environment reminders: one row per slot (08/12/17) per lab/location.
        times = ['08', '12', '17']
        slot_labels = {t: EnvironmentReminder(time=t).get_time_display() for t in times}
        locations = list(Location.objects.all())
        if not locations:
            locations = [None]
        for location in locations:
            lab_name = location.name if location else 'Lab'
            for time_val in times:
                reminder, was_created = EnvironmentReminder.objects.get_or_create(
                    date=today,
                    time=time_val,
                    location=location,
                    defaults={'is_recorded': False}
                )
                if was_created:
                    for user in personnel_users():
                        Notification.objects.create(
                            recipient=user,
                            message=f'Environment recording for {lab_name} due today at {slot_labels[time_val]} ({today}).',
                            link=reverse('environment_list') + (f'?location={location.pk}' if location else ''),
                            notification_type='environment_reminder',
                        )
                    created += 1

                # Slot-time nudge: only when the slot time has arrived, the slot is
                # still unrecorded, and we have not already nudged for this lab +
                # today + slot.
                slot_hour = int(time_val)
                nudge_marker = f'Reminder: environment recording for {lab_name} at {slot_labels[time_val]} today'
                nudge_sent = Notification.objects.filter(
                    notification_type='environment_reminder',
                    created_at__date=today,
                    message__contains=nudge_marker,
                ).exists()
                if (now.hour >= slot_hour and not reminder.is_recorded and not nudge_sent):
                    for user in personnel_users():
                        Notification.objects.create(
                            recipient=user,
                            message=nudge_marker + ' is still pending.',
                            link=reverse('environment_list') + (f'?location={location.pk}' if location else ''),
                            notification_type='environment_reminder',
                        )
                    created += 1

        # Primary recalibration reminders — flag primaries due within the next
        # 90 days (>= 3 months in advance) and mark overdue ones, notifying managers.
        due_soon = today + timedelta(days=90)
        primaries = Primary.objects.filter(
            status='active',
        ).exclude(calibration_due_date__isnull=True)
        due_primaries = primaries.filter(
            calibration_due_date__lte=due_soon
        ).distinct()

        for primary in due_primaries:
            due_in = (primary.calibration_due_date - today).days
            if due_in <= 0:
                primary.status = 'pending_maintenance'
                primary.save(update_fields=['status'])
            managers = get_users_with_perm('approve_calibration')
            for mgr in managers:
                Notification.objects.create(
                    recipient=mgr,
                    message=(
                        f'Primary "{primary.name}" ({primary.serial_no or "No serial"}) '
                        f'is due for recalibration on {primary.calibration_due_date}.'
                        if due_in >= 0 else
                        f'Primary "{primary.name}" ({primary.serial_no or "No serial"}) '
                        f'was due for recalibration on {primary.calibration_due_date} and is now overdue.'
                    ),
                    link=reverse('primary_detail', args=[primary.pk]),
                    notification_type='primary_due_reminder',
                )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f'Created {created} reminder(s) for {today}')
        )
