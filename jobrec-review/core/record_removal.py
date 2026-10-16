"""Reversible operational record removal. No physical row/file deletion."""
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

CHIEF_ROLES = {'Chief', 'Chief Meteorologist', 'Chief Metrologist'}


def can_remove(user):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    person = getattr(user, 'personnel_profile', None)
    return bool(person and person.role and person.role.name in CHIEF_ROLES | {'Administrator'})


def install_managers():
    """Default queries hide tombstones; base managers retain historical FK access.

    Historical migration models are untouched. Existing fields and approval state
    stay unchanged. Unfiltered access is deliberately limited to recovery code.
    """
    from django.apps import apps
    from app.modules.record_maintenance import EI_TYPES, EI_RETAINED
    from .models import AdministrativeArchive
    kinds = {value[0]:kind for kind,value in {**EI_TYPES, **EI_RETAINED}.items()}
    for name,kind in kinds.items():
        model = apps.get_model('core',name)
        manager = model._default_manager
        original_class = type(manager)

        def queryset(self, _kind=kind, _original=original_class):
            removed = AdministrativeArchive.objects.filter(target_type=_kind,restored_at__isnull=True).values('object_id')
            return _original.get_queryset(self).exclude(pk__in=models.Subquery(removed))

        manager.__class__ = type(name+'VisibleManager',(original_class,),{'get_queryset':queryset})


@login_required
@require_POST
def remove(request):
    if not can_remove(request.user):
        return JsonResponse({'error':'Only the Chief or Administrator can remove records.'},status=403)
    from app.modules.record_maintenance import change, EI_TYPES, EI_RETAINED
    from .ei_workflow import audit
    try:
        payload = json.loads(request.body)
        entries = validate(payload, set(EI_TYPES) | set(EI_RETAINED))
        with transaction.atomic():
            for kind,pk in entries:
                change(None,kind,pk,'archive',payload['reason'],request.user.get_full_name() or request.user.username)
                audit(request.user,None,'record_removed',after={'kind':kind,'id':pk,'reason':payload['reason']})
        return JsonResponse({'removed':len(entries)})
    except (ValueError,TypeError,KeyError) as error:
        return JsonResponse({'error':str(error)},status=400)


def validate(payload, allowed):
    if not isinstance(payload,dict) or not isinstance(payload.get('reason'),str) or len(payload['reason'].strip())<5:
        raise ValueError('Enter a removal reason of at least five characters.')
    rows = payload.get('records')
    if not isinstance(rows,list) or not 1<=len(rows)<=100:
        raise ValueError('Select between 1 and 100 records.')
    result = []
    for row in rows:
        if not isinstance(row,dict) or row.get('kind') not in allowed or type(row.get('id')) is not int or row['id']<1:
            raise ValueError('Invalid record selection.')
        item = (row['kind'],row['id'])
        if item not in result:
            result.append(item)
    return result


@login_required
@require_POST
def legacy_delete(request, pk, kind):
    """Keep bookmarked delete URLs recoverable; never cascade physical rows."""
    from django.contrib import messages
    from django.shortcuts import redirect
    from app.modules.record_maintenance import change
    from .ei_workflow import audit
    if not can_remove(request.user):
        return JsonResponse({'error':'Only the Chief or Administrator can remove records.'},status=403)
    reason=request.POST.get('reason','').strip()
    try:
        with transaction.atomic():
            change(None,kind,pk,'archive',reason,request.user.get_full_name() or request.user.username)
            audit(request.user,None,'record_removed',after={'kind':kind,'id':pk,'reason':reason})
        messages.success(request,'Record retained in the administrator master recycle bin.')
        return redirect('dashboard')
    except ValueError as error:
        return JsonResponse({'error':str(error)},status=400)
