"""Source application workspaces for monitoring, analytics and Chief registration."""
from datetime import date, timedelta
import csv
import hmac
import io


def register(app):
    from flask import abort, flash, redirect, render_template, request, session, url_for, Response
    from app.database.database import get_connection
    from app.modules import flow_environment as environment, flow_analytics

    def integrity_error(error):
        import sqlite3
        from django.db import IntegrityError,OperationalError
        if isinstance(error,(sqlite3.IntegrityError,IntegrityError)):
            return True
        if isinstance(error,(sqlite3.OperationalError,OperationalError)) and ('database is locked' in str(error).lower() or 'database is busy' in str(error).lower()):
            return True
        return type(error).__module__.startswith('psycopg') and type(error).__name__ in ('UniqueViolation','IntegrityError')

    def csrf():
        if not session.get('_admin_csrf') or not hmac.compare_digest(session['_admin_csrf'],request.form.get('_admin_csrf','')):
            abort(400, description='Reload the form before saving.')

    def csv_export(columns, rows, filename):
        stream=io.StringIO(newline=''); writer=csv.writer(stream)
        # Prevent spreadsheet formula execution for untrusted names and notes.
        def safe(value):
            if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
                return "'"+value
            return '' if value is None else value
        writer.writerow(columns)
        writer.writerows([[safe(v) for v in row] for row in rows])
        return Response('\ufeff'+stream.getvalue(),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"'})

    @app.route('/environment',methods=['GET','POST'])
    def flow_environment():
        from web_app import audit_change, current_actor
        from app.modules.auth.permissions import Permissions
        may_record=Permissions.can(session.get('role_name'),'equipment_edit')
        connection=get_connection(); form_error=False
        try:
            try:
                selected=environment.filters(request.args)
            except ValueError:
                abort(400,description='Enter a valid ordered date range.')
            if request.method=='POST':
                if not may_record: abort(403)
                csrf()
                try:
                    pk=environment.save(connection,request.form,session.get('user_id'),current_actor())
                    audit_change(connection,'flow_environment',pk,'create',after=dict(request.form, _admin_csrf='[redacted]'))
                    connection.commit(); flash('Environmental reading saved.','success')
                    return redirect(url_for('flow_environment'))
                except ValueError as error:
                    connection.rollback(); flash(str(error),'error'); form_error=True
                except Exception as error:
                    if not integrity_error(error): raise
                    connection.rollback(); flash('This reading conflicts with an existing record. Reload before trying again.','error'); form_error=True
            data=environment.records(connection,selected)
            if request.args.get('export')=='csv':
                return csv_export(('Reference','Date','Time','Location','Temperature °C','Humidity %','Pressure kPa','Instrument','Recorded by','Notes'),
                    [(f"{r['kind']}-{r['id']}",r['date'],r['time'],r['location'],r['temperature'],r['humidity'],r['pressure'],r['instrument'],r['recorder'],r['notes']) for r in data], 'FlowLab-Environmental-Records.csv')
            all_rows=environment.records(connection,{})
            try: days=int(request.args.get('days',30))
            except ValueError: days=30
            if days not in (7,30,90): days=30
            trend=[r for r in reversed(data) if str(r['date'])>=(date.today()-timedelta(days=days-1)).isoformat()]
            charts=[]
            # Distinct locations/slots remain identifiable in the table, with actual time spacing on the graph.
            from datetime import datetime
            for field,title in (('temperature','Temperature (°C)'),('humidity','Relative humidity (%)')):
                points=[r for r in trend if r[field] is not None]
                values=[float(r[field]) for r in points]
                low,high=(min(values),max(values)) if values else (0,1)
                span=high-low or 1
                moments=[]
                for r in points:
                    try: moment=datetime.fromisoformat(f"{r['date']}T{r['time'] or '00:00'}").timestamp()
                    except ValueError: moment=datetime.fromisoformat(str(r['date'])[:10]).timestamp()
                    moments.append(moment)
                first,last=(min(moments),max(moments)) if moments else (0,1)
                dots=[(round(45+(moment-first)/(last-first or 1)*435,2),round(148-(float(r[field])-low)/span*126,2)) for moment,r in zip(moments,points)]
                charts.append(dict(title=title,count=len(points),low=round(low,2),high=round(high,2),dots=dots,
                    points=' '.join(f'{x},{y}' for x,y in dots) if len({r['location'] for r in points})<=1 else '',
                    first=points[0]['date'] if points else '',last=points[-1]['date'] if points else ''))
            today=date.today().isoformat()
            today_rows=[r for r in all_rows if str(r['date'])==today and (not selected['location'] or r['location']==selected['location'])]
            return render_template('flow_environment.html',records=data[:200],total=len(data),selected=selected,
                locations=sorted({r['location'] for r in all_rows}|{'Flow Laboratory'}),today=today,charts=charts,trend_days=days,
                slots=[(slot,any(r['time']==slot for r in today_rows)) for slot in environment.SLOTS],may_record=may_record,
                form=request.form,form_error=form_error,page_title='Environmental Records',active_nav='iso17025')
        finally:
            connection.close()

    @app.get('/analytics',endpoint='flow_analytics')
    @app.get('/analytics/<category>',endpoint='flow_analytics')
    def flow_analytics_view(category='calibration'):
        from web_app import WORKSPACES
        modules=WORKSPACES['analytics']['modules']
        match=next((item for item in modules if item[0]==category),None)
        if not match: abort(404)
        try: selected=environment.filters(request.args)
        except ValueError: abort(400,description='Enter a valid ordered date range.')
        selected.pop('location')
        connection=get_connection()
        try: report=flow_analytics.report(connection,category,**{'start':selected['from_date'],'end':selected['to_date']})
        finally: connection.close()
        report['rows'].reverse()
        if request.args.get('export')=='csv':
            return csv_export(report['columns'],report['rows'],f'FlowLab-Analytics-{category}.csv')
        return render_template('flow_analytics.html',report=report,modules=modules,category=category,selected=selected,
            page_title=match[1],active_nav='analytics')

    @app.route('/personnel/register',methods=['GET','POST'])
    def chief_personnel():
        from web_app import ei_user_models, audit_change, current_actor, AuthService, add_notification
        from app.modules.integrated_accounts import admin_connection, shared_database
        if session.get('role_name') not in {'Chief Metrologist','Chief Meteorologist','Administrator','HOD'}:
            abort(403)
        ei_user_models()
        from core.models import Role, Personnel
        from core.personnel_records import assignable_roles
        connection=admin_connection()
        basic_roles=('Supervisor','Engineer','Technician','Operator','Guest')
        ei_roles=assignable_roles(None,administrative=False)
        error=False
        try:
            registration_id=request.values.get('registration_id',type=int)
            from app.database.database import database_backend
            lock=' FOR UPDATE' if request.method=='POST' and database_backend()=='postgresql' else ''
            registration=connection.execute('''SELECT id,full_name,email,requested_role,initiated_by_user_id FROM personnel_registrations
                WHERE id=? AND status='Pending' '''+lock,(registration_id,)).fetchone() if registration_id else None
            if registration_id and not registration:
                flash('This request has already been completed or is no longer pending.','success')
                return redirect(url_for('chief_personnel'))
            if request.method=='POST':
                csrf()
                lab=request.form.get('lab')
                try:
                    if lab not in ('flow','ei'): raise ValueError('Select a laboratory.')
                    if registration and lab!='flow': raise ValueError('This pending FlowLab registration must be completed in FlowLab.')
                    username=request.form.get('username','').strip()
                    name=request.form.get('full_name','').strip()
                    password=request.form.get('password','')
                    from django.contrib.auth.password_validation import validate_password
                    from django.contrib.auth.validators import UnicodeUsernameValidator
                    from django.core.exceptions import ValidationError
                    try:
                        UnicodeUsernameValidator()(username); validate_password(password)
                    except ValidationError as exc: raise ValueError(' '.join(exc.messages))
                    if not username or not name or len(password)<10: raise ValueError('Name, username and a temporary password of at least 10 characters are required.')
                    if lab=='flow':
                        role=request.form.get('flow_role','')
                        if role not in basic_roles: raise ValueError('Select a permitted personnel role.')
                        if connection.execute('SELECT id FROM users WHERE LOWER(username)=LOWER(?)',(username,)).fetchone():
                            raise ValueError('This FlowLab username already exists.')
                        role_id=connection.execute('SELECT id FROM roles WHERE name=?',(role,)).fetchone()[0]
                        pk=connection.execute('''INSERT INTO users(username,full_name,email,password_hash,role_id,is_active,must_change_password)
                            VALUES (?,?,?,?,?,1,1)''',(username,name,request.form.get('email','').strip(),AuthService.hash_password(password),role_id)).lastrowid
                    else:
                        if not shared_database(): raise ValueError('E&I registration requires the shared integrated database.')
                        from core.forms import PersonnelForm
                        values=request.form.to_dict()
                        values.update(name=name,login_username=username,temporary_password=password,role=values.get('ei_role'),
                            employment_status='active',experience_as_of=date.today().isoformat())
                        form=PersonnelForm(values)
                        form.fields['role'].queryset=ei_roles
                        if not form.is_valid(): raise ValueError('; '.join(f'{key}: {", ".join(errors)}' for key,errors in form.errors.items()))
                        from django.contrib.auth.models import User
                        person=form.save(commit=False)
                        person.user=User.objects.create_user(username=username,password=password,email=values.get('email',''))
                        person.save(); form.save_m2m(); pk=person.pk; role=person.role.name
                    audit_change(connection,'personnel' if lab=='flow' else 'ei_personnel',pk,'register',after={
                        'lab':lab,'name':name,'username':username,'role':role,'actor_flowlab_user_id':session['user_id'],
                        'technical_authorization':'Not granted by registration'})
                    if registration:
                        connection.execute("""UPDATE personnel_registrations SET status='Approved',completed_user_id=?,reviewed_at=CURRENT_TIMESTAMP
                            WHERE id=? AND status='Pending'""",(pk,registration_id))
                        connection.execute("""UPDATE workflow_tasks SET status='Completed',decision='approve',reviewed_at=CURRENT_TIMESTAMP
                            WHERE entity_type='personnel_registration' AND entity_id=? AND status='Pending'""",(registration_id,))
                        audit_change(connection,'personnel_registration',registration_id,'approve',after={'user_id':pk,'role':role})
                        add_notification(connection,registration[4],'Personnel registration completed',name,
                            url_for('personnel_record',user_id=pk),'personnel_registration',registration_id)
                    connection.commit(); flash(f'{name} registered in {"FlowLab Pro" if lab=="flow" else "E&I Lab"}. Technical authorization requires separate approval.','success')
                    return redirect(url_for('chief_personnel'))
                except ValueError as exc:
                    connection.rollback(); connection.close(); connection=admin_connection()
                    flash(str(exc),'error'); error=True
                except Exception as exc:
                    if not integrity_error(exc): raise
                    connection.rollback(); connection.close(); connection=admin_connection()
                    flash('This registration conflicts with an existing account. No partial registration was saved.','error'); error=True
            people=connection.execute('''SELECT u.id,u.full_name,u.username,r.name FROM users u JOIN roles r ON r.id=u.role_id WHERE u.is_active=1 ORDER BY u.full_name''').fetchall()
            pending=connection.execute("SELECT id,full_name,requested_role,initiated_by FROM personnel_registrations WHERE status='Pending' ORDER BY id").fetchall()
            displayed=request.form if request.method=='POST' else dict(full_name=registration[1],email=registration[2] or '',flow_role=registration[3]) if registration else {}
            return render_template('chief_personnel.html',flow_roles=basic_roles,ei_roles=list(ei_roles),people=people,
                pending=pending,registration_id=registration_id,form_error=error or bool(registration),form=displayed,
                page_title='Personnel Registration',active_nav='iso17025')
        finally: connection.close()
