from django.contrib.auth.models import User
from django.db.models import Q

from core.models import Personnel

AUTHORITY_ROLES = ('Administrator','Chief','Chief Metrologist','Chief Meteorologist','HOD')


def lab_authority(user):
    """Explicit E&I role policy, including the requested role-only sign-off exception."""
    if not user.is_authenticated or not user.is_active: return False
    if user.is_superuser: return True
    try:
        person=user.personnel_profile
        return bool(person.employment_status=='active' and person.role and person.role.name in AUTHORITY_ROLES)
    except (Personnel.DoesNotExist,AttributeError):
        return False


def has_perm(user, codename):
    if not user.is_authenticated or not user.is_active:
        return False
    if lab_authority(user):
        return True
    if codename in ('approve_calibration','authorize_personnel'):
        return False  # Final sign-off belongs to Chief / Administrator.
    try:
        return user.personnel_profile.employment_status=='active' and user.personnel_profile.role.permissions.filter(codename=codename).exists()
    except (Personnel.DoesNotExist, AttributeError):
        return False


def get_users_with_perm(codename):
    """Users holding `codename` via their role, plus all superusers (mirrors
    `has_perm`, which treats superusers as having every permission)."""
    authority=Q(personnel_profile__role__name__in=AUTHORITY_ROLES,personnel_profile__employment_status='active')|Q(is_superuser=True)
    permitted=Q(personnel_profile__role__permissions__codename=codename,personnel_profile__employment_status='active')
    return User.objects.filter(authority if codename in ('approve_calibration','authorize_personnel') else authority|permitted,is_active=True).distinct()


def get_user_signature_url(user):
    """URL of the user's uploaded profile signature ('' when none or no profile).

    Signatures are uploaded once on the profile page and auto-populated onto
    calibration logs the user creates (technician) or approves (QHSE)."""
    try:
        return user.personnel_profile.signature_url
    except (Personnel.DoesNotExist, AttributeError):
        return ''
