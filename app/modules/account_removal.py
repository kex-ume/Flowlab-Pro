"""Administrator-only recoverable removal of login identities, never audit rows."""
from django.utils import timezone


def archive(connection, entries, reason, actor, current_id):
    from core.models import AdminAccountLink, AdministrativeArchive, User
    from django.db.models import Q
    from app.modules.integrated_accounts import guard_last_admin
    current=connection.execute('SELECT username FROM users WHERE id=?',(current_id,)).fetchone()
    if not current: raise ValueError('Signed-in administrator was not found.')
    for kind,pk in entries:
        if kind=='flow_user':
            row=connection.execute('SELECT id,username,is_active FROM users WHERE id=?',(pk,)).fetchone()
            if not row: raise ValueError('Account was not found.')
            link=AdminAccountLink.objects.filter(flowlab_user_id=pk).select_related('user').first()
            ei=link.user if link else None
        else:
            ei=User.objects.filter(pk=pk).first()
            if not ei: raise ValueError('Account was not found.')
            link=AdminAccountLink.objects.filter(user=ei).first()
            row=connection.execute('SELECT id,username,is_active FROM users WHERE id=?',(link.flowlab_user_id,)).fetchone() if link else None
        if row and row[0]==current_id:
            raise ValueError('You cannot remove your own signed-in account.')
        if ei and ei.username.lower()==current[0].lower():
            raise ValueError('You cannot remove your own signed-in identity.')
        if row: guard_last_admin(connection,row[0])
        if ei and ei.is_active and (ei.is_superuser or getattr(getattr(ei,'personnel_profile',None),'role',None) and ei.personnel_profile.role.name=='Administrator'):
            if not User.objects.filter(is_active=True).filter(Q(is_superuser=True)|Q(personnel_profile__role__name='Administrator')).exclude(pk=ei.pk).exists():
                raise ValueError('The last active E&I Administrator cannot be removed.')
        targets=([('flow_user',row[0])] if row else [])+([('ei_user',ei.pk)] if ei else [])
        if any(AdministrativeArchive.objects.filter(target_type=k,object_id=i,restored_at__isnull=True).exists() for k,i in targets):
            raise ValueError('This account has already been removed.')
        state={'account':True,'flow_id':row[0] if row else None,'ei_id':ei.pk if ei else None,'flow_active':bool(row[2]) if row else False,'ei_active':bool(ei.is_active) if ei else False,'display':row[1] if row else ei.username}
        if row: connection.execute('UPDATE users SET is_active=0 WHERE id=?',(row[0],))
        if ei:
            ei.is_active=False
            ei.save(update_fields=['is_active'])
        for target,identity in targets:
            AdministrativeArchive.objects.update_or_create(target_type=target,object_id=identity,defaults={'previous_state':state,'reason':reason,'actor_name':actor,'archived_at':timezone.now(),'restored_at':None})


def restore(connection, entry, reason, actor):
    from core.models import AdministrativeArchive, User
    state=entry.previous_state
    if not state.get('account'):
        raise ValueError('Not a retained account.')
    flow_id,ei_id=state.get('flow_id'),state.get('ei_id')
    if flow_id:
        if not connection.execute('SELECT id FROM users WHERE id=?',(flow_id,)).fetchone():
            raise ValueError('Original FlowLab account is missing; restore was cancelled.')
        connection.execute('UPDATE users SET is_active=? WHERE id=?',(int(state['flow_active']),flow_id))
    if ei_id:
        user=User.objects.filter(pk=ei_id).first()
        if not user: raise ValueError('Original E&I account is missing; restore was cancelled.')
        user.is_active=state['ei_active'];user.save(update_fields=['is_active'])
    for target,identity in (('flow_user',flow_id),('ei_user',ei_id)):
        if identity:
            row=AdministrativeArchive.objects.filter(target_type=target,object_id=identity,restored_at__isnull=True).first()
            if row:
                row.restored_at=timezone.now();row.reason+='\nRestored: '+reason;row.actor_name=actor
                row.save(update_fields=['restored_at','reason','actor_name'])
