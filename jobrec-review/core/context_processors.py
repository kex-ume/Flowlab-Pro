from django.templatetags.static import static

from .models import CompanyProfile, Job, Notification, Personnel


def notification_count(request):
    if request.user.is_authenticated:
        count = Notification.objects.filter(
            recipient=request.user, is_read=False
        ).count()
        pending = Job.objects.exclude(
            job_status__in=['not_received', 'completed', 'dispatched']
        ).count()
        return {'unread_notification_count': count, 'pending_job_count': pending}
    return {}


def record_removal_controls(request):
    from .record_removal import can_remove
    return {'can_remove_records':can_remove(request.user)}


def breadcrumb_navigation(request):
    if not request.user.is_authenticated:
        return {'breadcrumbs':[]}
    from django.urls import reverse
    from app.navigation import ei_breadcrumbs
    match=request.resolver_match
    return {'breadcrumbs':ei_breadcrumbs(request.path,reverse('dashboard'),match.url_name if match else '',request.GET.dict())}


def company_logo(request):
    """Brand logo for the site chrome, mirrors the calibration certificate:
    use the uploaded company logo, else fall back to the EATL logo asset."""
    company = CompanyProfile.objects.first()
    if company and company.logo:
        return {'company_logo': company.logo.url}
    return {'company_logo': static('core/images/image2.jpeg')}
