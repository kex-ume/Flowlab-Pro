"""Read-only operational analytics. No placeholder metrics or duplicate records."""
from collections import Counter
from datetime import date


def report(connection, category, start='', end=''):
    today = date.today().isoformat()
    def rows(sql, field):
        predicates, params = [], []
        if start:
            predicates.append(f'CAST({field} AS TEXT)>=?'); params.append(start)
        if end:
            predicates.append(f'SUBSTR(CAST({field} AS TEXT),1,10)<=?'); params.append(end)
        return connection.execute(sql + (' AND ' + ' AND '.join(predicates) if predicates else '') + f' ORDER BY {field}', params).fetchall()
    job_active = "j.is_deleted=0 AND NOT EXISTS (SELECT 1 FROM project_jobs pj JOIN projects p ON p.id=pj.project_id WHERE pj.job_id=j.id AND p.is_deleted=1)"
    if category == 'calibration':
        columns = ('Job', 'Status', 'Required date', 'Started', 'Completed')
        data = rows(f'SELECT j.job_number,j.status,j.required_date,j.started_at,j.completed_at FROM calibration_jobs j WHERE {job_active}', 'j.created_at')
        status = Counter(str(r[1]) for r in data)
        completed = [r for r in data if r[1] == 'Completed']
        days=[]
        for r in completed:
            try:
                elapsed=(date.fromisoformat(str(r[4])[:10])-date.fromisoformat(str(r[3])[:10])).days
                if elapsed >= 0: days.append(elapsed)
            except (ValueError, TypeError): pass
        metrics = [('Jobs',len(data)),('Completed',len(completed)),('Overdue',sum(bool(r[2] and str(r[2])[:10]<today and r[1] not in ('Completed','Cancelled')) for r in data)),('Mean turnaround (days)',round(sum(days)/len(days),1) if days else '—')]
        note = 'Turnaround uses completed jobs with both valid start and completion dates. Deleted jobs/projects are excluded.'
    elif category in ('uncertainty','cmc'):
        columns = ('Calculation','Job','Revision','Status','Flow point','Flow unit','Expanded U (%)','Applicable CMC (%)','Comparison')
        data = rows(f'''SELECT c.calculation_uid,j.job_number,c.revision,c.status,f.label,f.flow_unit,
            r.expanded_uncertainty,r.applicable_cmc,r.comparison_status FROM uncertainty_calculations c
            JOIN calibration_jobs j ON j.id=c.job_id LEFT JOIN uncertainty_flow_points f ON f.calculation_id=c.id
            LEFT JOIN uncertainty_point_results r ON r.flow_point_id=f.id
            WHERE c.status NOT IN ('Deleted','Superseded') AND {job_active}''', 'c.created_at')
        unique = {(r[0],r[1],r[2]) for r in data}
        status = Counter(r[3] for r in {tuple(r[:4]) for r in data})
        compared = [r for r in data if r[6] is not None and r[7] is not None]
        metrics = [('Budgets',len(unique)),('Calculated points',sum(r[6] is not None for r in data)),('Points with CMC',len(compared)),('U below CMC',sum(r[6]<r[7] for r in compared))]
        note = 'Point values retain their recorded basis and units; unlike units are never averaged. Below-CMC results require review, not an automatic conformity decision. Draft results are labelled by status.'
    elif category == 'equipment':
        columns = ('Asset','Equipment','Status','Last calibration','Next calibration')
        data = rows('''SELECT asset_number,equipment_name,status,last_calibration_date,next_calibration_date
            FROM laboratory_equipment WHERE is_active=1''','created_at')
        status = Counter(r[2] or 'Not specified' for r in data)
        metrics = [('Lab equipment',len(data)),('Overdue',sum(bool(r[4] and str(r[4])[:10]<today) for r in data)),('Due within 30 days',sum(bool(r[4] and today<=str(r[4])[:10]<=date.fromordinal(date.today().toordinal()+30).isoformat()) for r in data)),('No due date',sum(not r[4] for r in data))]
        note = 'Laboratory assets only, not client UUTs. Date filters select asset registration dates. Drift/reliability is not inferred without comparable measurement history.'
    elif category == 'capa':
        columns = ('NCR','Title','Status','Owner','Target closure','Closed')
        data = rows('SELECT ncr_number,title,status,owner,target_close_date,closed_at FROM capa_records WHERE is_deleted=0','issued_date')
        status = Counter(r[2] for r in data)
        metrics = [('CAPA records',len(data)),('Closed',sum(bool(r[5]) for r in data)),('Overdue',sum(bool(r[4] and str(r[4])[:10]<today and not r[5]) for r in data)),('Pending closure',sum(not r[5] for r in data))]
        note = 'Counts come from the controlled CAPA register. Closure is counted only when a closure timestamp exists.'
    elif category == 'audit-pt':
        columns = ('Reference','Title','Status','Owner','Due date','Closed')
        data = rows("SELECT reference_number,title,status,owner,due_date,closed_at FROM quality_records WHERE is_deleted=0 AND record_type='audit-pt'",'created_at')
        status = Counter(r[2] for r in data)
        metrics = [('Audit / PT records',len(data)),('Closed',sum(bool(r[5]) for r in data)),('Overdue',sum(bool(r[4] and str(r[4])[:10]<today and not r[5]) for r in data)),('Open',sum(not r[5] for r in data))]
        note = 'Audit / PT programme records only. PT scores and pass rates are not invented when structured scores are unavailable.'
    else:
        raise ValueError('Unknown analytics report.')
    peak=max(status.values(),default=1)
    return dict(columns=columns, rows=data, metrics=metrics, note=note,
                bars=[{'label':key,'count':value,'width':round(value/peak*100)} for key,value in sorted(status.items())])
