"""Read-only breadcrumb builders. Every URL points to an existing GET page."""
from urllib.parse import urlencode
from urllib.parse import urlsplit


def _add(trail, label, url):
    if not trail or trail[-1]['url'] != url:
        trail.append({'label':str(label), 'url':url, 'current':False})


def _finish(trail, label, url):
    if trail[-1]['url'] == url or trail[-1]['label']==label and urlsplit(trail[-1]['url']).path==urlsplit(url).path:
        if label: trail[-1]['label']=str(label)
        trail[-1]['url']=url
    else:
        _add(trail,label or 'Overview',url)
    trail[-1]['current']=True
    return trail


def flow_breadcrumbs(path, query=None, title=None, selected_project=None, workspace_titles=None):
    query=query or {}
    current=path+('?' + urlencode(query) if query else '')
    trail=[{'label':'FlowLab Pro','url':'/dashboard','current':False}]
    parts=path.strip('/').split('/')
    if path=='/dashboard': return _finish(trail,'FlowLab Pro',current)
    if parts[0]=='workspace' and len(parts)>1:
        section=parts[1]
        label=(workspace_titles or {}).get(section,section.replace('-',' ').title())
        _add(trail,label,'/workspace/'+section)
    elif parts[0]=='analytics':
        _add(trail,'Analytics','/analytics')
    elif parts[0] in {'environment','personnel'}:
        _add(trail,'ISO 17025','/workspace/iso17025')
    elif parts[0]=='projects':
        _add(trail,'Projects','/projects/jobs')
        project=query.get('project','')
        if selected_project:
            _add(trail,selected_project[1],'/projects/jobs?'+urlencode({'project':selected_project[0]}))
            if path=='/projects/jobs': title=selected_project[1]
        elif str(project).isdigit():
            _add(trail,'Project '+str(project),'/projects/jobs?'+urlencode({'project':project}))
        if len(parts)>2 and parts[1]=='jobs' and parts[2].isdigit() and len(parts)>3:
            _add(trail,'Job Record','/projects/jobs/'+parts[2])
        elif len(parts)>2 and parts[1].isdigit():
            _add(trail,'Project Record','/projects/jobs?'+urlencode({'project':parts[1]}))
    elif parts[0]=='equipment' or parts[0]=='programme':
        _add(trail,'ISO 17025','/workspace/iso17025')
        _add(trail,'Laboratory Equipment','/equipment')
        if len(parts)>1 and parts[1].isdigit() and (len(parts)>2 or query.get('tab')):
            _add(trail,'Equipment Record','/equipment/'+parts[1])
    elif parts[0]=='iso17025':
        _add(trail,'ISO 17025','/workspace/iso17025')
        if len(parts)>1 and parts[1]=='clause-checklist':
            _add(trail,'Clause Checklist','/iso17025/clause-checklist')
            if len(parts)>3 and parts[2].isdigit() and parts[3]!='personnel':
                _add(trail,'Clause Record','/iso17025/clause-checklist/'+parts[2])
        elif len(parts)>1 and parts[1]=='clause-scope':
            _add(trail,'Scope','/iso17025/clause-scope')
        else:
            _add(trail,'Clause Checklist','/iso17025/clause-checklist')
    elif parts[0]=='capa':
        _add(trail,'ISO 17025','/workspace/iso17025')
        _add(trail,'CAPA & NCR','/capa')
    elif parts[0]=='uncertainty':
        _add(trail,'ISO 17025','/workspace/iso17025')
        _add(trail,'Uncertainty Management','/uncertainty')
        view=query.get('view')
        if view: title={'calculator':'Calculator','records':'Calculation Records','cmc':'CMC','configuration':'Configuration','sources':'Uncertainty Sources','matrix':'Equipment Matrix'}.get(view,title)
    elif parts[0]=='tools':
        _add(trail,'Tools','/tools')
    elif parts[0]=='documents':
        _add(trail,'Standards & Procedures','/workspace/standards')
        _add(trail,'Controlled Documents','/documents')
    elif parts[0] in {'settings','users'}:
        _add(trail,'Settings','/settings')
    elif parts[0]=='recycle-bin':
        _add(trail,'Recycle Bin','/recycle-bin')
    elif parts[0]=='workflow':
        _add(trail,'Notifications','/reminders')
    return _finish(trail,title,current)


def ei_breadcrumbs(path, root, route_name='', query=None):
    """root is reversed by Django, preserving the integrated URL prefix."""
    query=query or {}
    relative=path[len(root):] if path.startswith(root) else path.lstrip('/')
    parts=relative.strip('/').split('/') if relative.strip('/') else []
    trail=[{'label':'E&I Lab','url':root,'current':False}]
    url=lambda suffix:root+suffix
    current=path+('?' + urlencode(query) if query else '')
    labels={
        'dashboard':'E&I Lab', 'job_list':'Job Records', 'job_detail':'Job Record',
        'job_create':'Add New Job','job_update':'Edit Job','ei_job_edit':'Edit Job',
        'ei_uut_workspace':'UUT Record','ei_record_view':'Technical Record',
        'personnel_list':'Personnel','personnel_detail':'Personnel Record',
        'ei_personnel_workspace':'Personnel Record','personnel_create':'Add Personnel',
        'personnel_update':'Edit Personnel','client_list':'Client Records',
        'client_detail':'Client Record','client_create':'Add Client','client_update':'Edit Client',
        'equipment_list':'Laboratory Equipment','ei_equipment_detail':'Equipment Record',
        'primary_list':'Reference Standards','primary_detail':'Reference Standard',
        'primary_create':'Add Equipment','primary_update':'Edit Equipment',
        'ei_calibration_programme':'Calibration Programme','ei_received_equipment':'Client Equipment (UUT)',
        'environment_list':'Environmental Log','environment_create':'Add Environmental Reading',
        'calibration_log_list':'Calibration Logs','calibration_log_detail':'Calibration Record',
        'calibration_log_create':'New Calibration Log','calibration_log_update':'Edit Calibration Log',
        'pre_calibration_list':'Pre-calibration','pre_calibration_detail':'Pre-calibration Record',
        'pre_calibration_create':'New Pre-calibration','waybill_list':'Waybills',
        'incoming_waybill_create':'New Incoming Waybill','outgoing_waybill_create':'New Outgoing Waybill',
        'waybill_detail':'Incoming Waybill','outgoing_waybill_detail':'Outgoing Waybill',
        'entry_dispatch':'Entry & Dispatch','procedure_list':'Procedures','procedure_detail':'Procedure Record',
        'procedure_assign':'Assign Procedure','procedure_edit':'Edit Procedure',
        'ei_retained_records':'Retained Records','ei_capa_list':'CAPA & NCR','ei_capa_detail':'CAPA Record',
        'settings':'Settings','scope_cert_template':'Certificate Layout','scope_uncertainty_budget':'Uncertainty Budget',
        'ei_log_templates':'Calibration Log Templates','ei_scope_templates':'Scope Log Templates',
        'profile':'My Profile','profile_edit':'Edit Profile','password_change':'Change Password',
        'notification_list':'Notifications', 'documents_archive':'Documents',
    }
    title=labels.get(route_name,route_name.removeprefix('ei_').replace('_',' ').title() or 'Overview')
    if not parts: return _finish(trail,'E&I Lab',current)
    first=parts[0]
    if first in {'personnel','clients','equipment','primaries','environment','records'}:
        _add(trail,'Records',url('records/retained/'))
        registers={'personnel':('Personnel','personnel/'),'clients':('Client Records','clients/'),
                   'equipment':('Laboratory Equipment','equipment/'),'primaries':('Reference Standards','primaries/'),
                   'environment':('Environmental Log','environment/')}
        if first=='equipment' and len(parts)>1 and parts[1]=='received':
            _add(trail,'Client Equipment (UUT)',url('equipment/received/'))
        elif first in registers: _add(trail,registers[first][0],url(registers[first][1]))
        if first=='personnel' and len(parts)>2 and parts[1].isdigit() and parts[2]!='competency':
            _add(trail,'Personnel Record',url('personnel/'+parts[1]+'/competency/'))
        if first in {'equipment','primaries'} and len(parts)>2 and parts[1].isdigit():
            _add(trail,'Equipment Record',url(first+'/'+parts[1]+'/'))
    elif first in {'jobs','waybills','calibration-logs','pre-calibration'}:
        _add(trail,'Jobs',url('jobs/'))
        registers={'waybills':('Waybills','waybills/'),'calibration-logs':('Calibration Logs','calibration-logs/'),
                   'pre-calibration':('Pre-calibration','pre-calibration/')}
        if first in registers: _add(trail,registers[first][0],url(registers[first][1]))
        if len(parts)>2 and parts[1].isdigit():
            _add(trail,{'jobs':'Job Record','calibration-logs':'Calibration Record','pre-calibration':'Pre-calibration Record'}.get(first,'Record'),url(first+'/'+parts[1]+'/'))
    elif first in {'documents','procedures','log-templates'}:
        _add(trail,'Documents',url('documents/'))
        if first=='procedures': _add(trail,'Procedures',url('procedures/'))
    elif first=='settings':
        _add(trail,'Settings',url('settings/'))
        if len(parts)>1:
            tab=parts[1]
            _add(trail,{'scopes':'Scopes','company':'Company','roles':'Roles','permissions':'Permissions','addresses':'Addresses'}.get(tab,tab.replace('-',' ').title()),url('settings/'+tab+'/'))
            if route_name=='settings_tab': title=trail[-1]['label']
    elif first=='capa':
        _add(trail,'CAPA & NCR',url('capa/'))
    elif first=='profile':
        _add(trail,'My Profile',url('profile/'))
    return _finish(trail,title,current)
