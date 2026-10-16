"""E&I-only personnel compliance and explicit technical-officer permissions."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import Personnel, Notification, PersonnelReviewReminder

OFFICER_PERMISSIONS = ('verify_personnel_records', 'assess_personnel_competency', 'authorize_personnel')


def assignable_roles(user, administrative=None):
    """Personnel maintenance must not allow appointing system/technical officers."""
    from .models import Role
    if administrative is None:
        administrative = bool(user and user.is_active and (user.is_superuser or
            Personnel.objects.filter(user=user,role__name='Administrator',employment_status='active').exists()))
    roles=Role.objects.all()
    from .auth_utils import lab_authority
    if administrative is not False and user and lab_authority(user) and not administrative:
        return roles.exclude(name='Administrator').order_by('name')
    if not administrative:
        privileged=Role.objects.filter(permissions__codename__in=(
            'manage_roles','administer_lab','manage_personnel','approve_calibration',
            'review_calibration',*OFFICER_PERMISSIONS)).values_list('pk',flat=True)
        roles=roles.exclude(pk__in=privileged).exclude(name__in=('Administrator','Chief Metrologist','Chief Meteorologist','HOD'))
    return roles.order_by('name')


def designated(user, permission):
    from .auth_utils import lab_authority
    if lab_authority(user): return True
    if permission=='authorize_personnel': return False
    return bool(user.is_active and Personnel.objects.filter(user=user,
        employment_status='active', role__permissions__codename=permission).exists())


def flags(user):
    from .auth_utils import has_perm
    from .ei_workflow import supervisor
    return {'may_manage': has_perm(user, 'manage_personnel') or supervisor(user),
            'may_verify': designated(user, 'verify_personnel_records'),
            'may_assess': designated(user, 'assess_personnel_competency'),
            'may_authorize': designated(user, 'authorize_personnel')}


def authorized_log(user, log, activity):
    from .ei_workflow import authorized
    person=Personnel.objects.filter(user=user).first()
    scopes=list(log.scopes.all()) if log.pk else []
    if log.scope_id and log.scope not in scopes: scopes.append(log.scope)
    return bool(scopes and all(authorized(person,activity,scope) for scope in scopes))


def validate_analyst(person, scopes):
    from django.core.exceptions import PermissionDenied
    from .ei_workflow import authorized
    if not person or not scopes or not all(authorized(person,'perform',scope) for scope in scopes):
        raise PermissionDenied('Select an active analyst with current competency and authorization for every selected scope.')


def badge(code, detail=''):
    return {'code': code, 'label': {'active':'Active','missing':'Not Uploaded','expired':'Expired','pending':'Pending Review'}[code], 'detail':detail}


def authorization_status(person, grant):
    today=timezone.localdate()
    if person.employment_status != 'active' or not person.user.is_active: return 'Inactive'
    if grant.revoked_at: return 'Revoked / Superseded'
    if grant.suspended_at: return 'Suspended'
    if grant.expires_on and grant.expires_on < today: return 'Expired'
    if grant.effective_from > today: return 'Pending Review'
    return 'Active'


def compliance(person):
    today = timezone.localdate()
    def evidence(kind):
        rows = [x for x in person.evidence.all() if x.kind == kind and x.status != 'superseded']
        if not rows: return badge('missing')
        if any(x.status == 'pending' for x in rows): return badge('pending')
        if any(x.expires_on and x.expires_on < today for x in rows): return badge('expired')
        return badge('active')
    assessments = list(person.competencies.filter(revisions__isnull=True))
    competency = badge('missing')
    if assessments:
        competency = badge('expired' if any(x.expires_on and x.expires_on < today for x in assessments)
            else 'pending' if any(x.result != 'competent' or x.assessed_on > today for x in assessments) else 'active')
    authorizations = list(person.authorizations.all())
    # Superseded grants stay in history, but do not colour the current dashboard.
    replaced = {x.previous_id for x in authorizations if x.previous_id}
    authorizations = [x for x in authorizations if x.pk not in replaced]
    authorization = badge('missing')
    if authorizations:
        expired = any(x.revoked_at or x.suspended_at or x.expires_on and x.expires_on < today for x in authorizations)
        authorization = badge('expired' if expired else 'pending' if any(x.effective_from > today for x in authorizations) else 'active',
            'Suspended / revoked' if any(x.suspended_at or x.revoked_at for x in authorizations) else '')
    if person.employment_status != 'active' or not person.user.is_active:
        authorization = badge('expired','Personnel inactive')
    return {'qualification': evidence('qualification'), 'training': evidence('training'),
            'competency': competency, 'authorization': authorization}


def evaluate_personnel_reviews(today=None):
    today = today or timezone.localdate()
    for person in Personnel.objects.select_related('user').filter(employment_status='active'):
        records = list(person.evidence.filter(status='verified',expires_on__isnull=False)) + list(person.competencies.filter(revisions__isnull=True,expires_on__isnull=False)) + list(person.authorizations.filter(revoked_at__isnull=True,expires_on__isnull=False))
        for row in records:
            if row.expires_on > today + timedelta(days=30): continue
            phase = 'expired' if row.expires_on < today else 'upcoming'
            key = f'{row._meta.model_name}:{row.pk}:{row.expires_on}:{phase}'
            permission = 'authorize_personnel' if row._meta.model_name == 'personnelauthorization' else 'assess_personnel_competency' if row._meta.model_name == 'personnelcompetency' else 'verify_personnel_records'
            from .auth_utils import get_users_with_perm
            recipients = list(get_users_with_perm(permission).values_list('pk',flat=True))
            if not recipients: continue
            with transaction.atomic():
                _, created = PersonnelReviewReminder.objects.get_or_create(key=key)
                if created:
                    for user_id in set(recipients):
                        Notification.objects.create(recipient_id=user_id,notification_type='personnel_review',
                            message=f'Personnel {person.pk} · {person.name}: {row._meta.verbose_name} review {phase}, due {row.expires_on}.',
                            link=f'/ei-lab/personnel/{person.pk}/competency/')
