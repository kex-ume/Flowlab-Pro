from django.urls import reverse
from django.utils import timezone

from core.auth_utils import get_users_with_perm
from core.models import Job, Notification, Personnel


def notify_users(recipients, message, link, notification_type):
    """Create a notification for each recipient, deduped and null-guarded."""
    seen = set()
    for user in recipients:
        if user is None or user.pk in seen:
            continue
        seen.add(user.pk)
        Notification.objects.create(
            recipient=user,
            message=message,
            link=link,
            notification_type=notification_type,
        )


def personnel_users(exclude_user=None):
    """Every User linked to a Personnel profile (used for broadcast
    notifications to all personnel), optionally excluding one user."""
    users = [
        p.user for p in Personnel.objects.select_related('user')
        .exclude(user__isnull=True) if p.user
    ]
    if exclude_user:
        users = [u for u in users if u.pk != exclude_user.pk]
    return users


def calibration_log_recipients(log):
    """Technician(s) involved in a calibration log: the creator (User FK) and
    the calibrator (Personnel.user), deduped, null-guarded."""
    recipients = []
    if log.recorded_by_id:
        recipients.append(log.recorded_by)
    if log.calibrated_by_id and log.calibrated_by.user_id:
        recipients.append(log.calibrated_by.user)
    return recipients


def send_overdue_job_reminders():
    """Send one reminder per overdue job per day to leads and assignees."""
    today = timezone.localdate()
    count = 0
    jobs = Job.objects.select_related('client').prefetch_related('assigned_to__user').filter(workflow_managed=False,
        scheduled_end_date__lt=today,
    ).exclude(job_status__in=['completed', 'dispatched']).exclude(delay_notified_on=today)
    supervisors = list(get_users_with_perm('review_pre_calibration'))
    for job in jobs:
        # Conditional update prevents duplicate reminders from concurrent page visits.
        claimed = Job.objects.filter(pk=job.pk).exclude(delay_notified_on=today).update(delay_notified_on=today)
        if not claimed:
            continue
        recipients = supervisors + [person.user for person in job.assigned_to.all() if person.user_id]
        notify_users(
            recipients,
            f'Overdue job for {job.client.name} (PO {job.purchase_order_number or "not recorded"}) was due {job.scheduled_end_date}. Update its status and enter a compulsory delay remark.',
            reverse('job_detail', args=[job.pk]),
            'job_overdue',
        )
        count += 1
    return count
