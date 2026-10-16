/* Explicit URL/attribute mapping only: never infer record IDs from visible text. */
(() => {
  const config = document.getElementById('recordRemovalConfig');
  if (!config) return;
  const ei = config.dataset.module === 'ei';
  const accounts = config.dataset.module === 'accounts';
  const rules = accounts ? [] : ei ? [
    [/^\/ei-lab\/personnel\/records\/competency\/(\d+)\//,'ei_competency'],
    [/^\/ei-lab\/personnel\/records\/authorization\/(\d+)\//,'ei_authorization'],
    [/^\/ei-lab\/personnel\/evidence\/(\d+)\//,'ei_training'],
    [/^\/ei-lab\/capa\/documents\/(\d+)\//,'ei_capa_document'],
    [/^\/ei-lab\/jobs\/(\d+)\//,'ei_job'],
    [/^\/ei-lab\/jobs\/workflow\/(\d+)\//,'ei_job'],
    [/^\/ei-lab\/jobs\/uuts\/(\d+)\//,'ei_uut'],
    [/^\/ei-lab\/jobs\/records\/(\d+)\//,'ei_technical'],
    [/^\/ei-lab\/clients\/(\d+)\//,'ei_client'],
    [/^\/ei-lab\/personnel\/(\d+)\/(?:competency\/|edit\/)?$/,'ei_personnel'],
    [/^\/ei-lab\/(?:equipment|primaries)\/(\d+)\//,'ei_equipment'],
    [/^\/ei-lab\/equipment\/records\/(\d+)\//,'ei_equipment_record'],
    [/^\/ei-lab\/procedures\/(\d+)\//,'ei_procedure'],
    [/^\/ei-lab\/pre-calibration\/(\d+)\//,'ei_precal'],
    [/^\/ei-lab\/calibration-logs\/(\d+)\//,'ei_calibration'],
    [/^\/ei-lab\/capa\/(\d+)\//,'ei_capa'],
    [/^\/ei-lab\/waybills\/(?:incoming\/|outgoing\/)?(\d+)\//,'ei_waybill']
  ] : [
    [/^\/projects\/(\d+)\/(?:edit|delete)$/,'flow_project'],
    [/^\/projects\/jobs\/(\d+)(?:\/|$)/,'flow_job'],
    [/^\/equipment\/\d+\/calibration\/(\d+)\//,'flow_calibration'],
    [/^\/equipment\/\d+\/maintenance\/(\d+)\//,'flow_maintenance'],
    [/^\/equipment\/(\d+)(?:\/(?:edit|delete))?$/,'flow_equipment'],
    [/^\/documents\/(\d+)\/delete$/,'flow_document'],
    [/^\/quality-records\/(\d+)\/delete$/,'flow_quality'],
    [/^\/tools\/decision-rule\/(\d+)\/delete$/,'flow_decision'],
    [/^\/generated-covers\/(\d+)\/delete$/,'flow_cover'],
    [/^\/iso17025\/personnel-documents\/(\d+)\/(?:delete|file)$/,'flow_personnel_document'],
    [/^\/uncertainty\/records\/(\d+)\//,'flow_uncertainty']
  ];
  function identify(value) {
    try {
      const url = new URL(value, location.href);
      if (url.origin !== location.origin) return null;
      if (!ei && url.pathname === '/projects/jobs' && /^\d+$/.test(url.searchParams.get('project') || '')) return {kind:'flow_project',id:Number(url.searchParams.get('project'))};
      for (const [pattern,kind] of rules) {
        const match = url.pathname.match(pattern);
        if (match) return {kind,id:Number(match[1])};
      }
    } catch (_) { /* Not a record URL. */ }
    return null;
  }
  const groups = new Map();
  function add(node, record) {
    if (!node || !record || node.closest('form[data-autosave-draft]')) return;
    const area = node.closest('table') || node.parentElement;
    if (!groups.has(area)) groups.set(area,new Map());
    if (!groups.get(area).has(node)) groups.get(area).set(node,record);
  }
  document.querySelectorAll('[data-record-kind][data-record-id]').forEach(node => add(node,{kind:node.dataset.recordKind,id:Number(node.dataset.recordId)}));
  document.querySelectorAll('main tbody tr, main article.project-card, main article.project-job-card').forEach(node => {
    if (node.dataset.recordKind) return;
    const candidates = [...node.querySelectorAll('form[action],a[href]')];
    const identified = candidates.map(item => identify(item.action || item.href)).filter(Boolean);
    const distinct = [...new Map(identified.map(x=>[x.kind+':'+x.id,x])).values()];
    // Ambiguous links must never select a related parent instead of this row.
    if (distinct.length===1) add(node,distinct[0]);
  });
  {
    const record = identify(location.href);
    const main = document.querySelector('main.content') || document.querySelector('main.fl-main');
    if (main && record) add(main.querySelector('section.ei-record-card, section.panel, section, article') || main,record);
  }
  groups.forEach((records,area) => {
    records.forEach((record,node)=>node.querySelectorAll('form[action]').forEach(form=>{
      if (/\/delete\/?$/.test(new URL(form.action,location.href).pathname)) {form.hidden=true;form.style.setProperty('display','none','important');}
    }));
    records.forEach((record,node)=>node.querySelectorAll('a[href]').forEach(link=>{
      if (/\/delete\/?$/.test(new URL(link.href,location.href).pathname)) {link.hidden=true;link.style.setProperty('display','none','important');}
    }));
    const tools = document.createElement('div'); tools.className = 'record-removal-tools';
    tools.innerHTML = '<span class="record-removal-status" role="status" hidden></span><button type="button" class="record-remove-confirm" hidden>Remove selected</button><button type="button" class="record-remove-cancel" hidden>Cancel</button><button type="button" class="record-remove-toggle" aria-label="Select records to remove" title="Select records to remove" aria-expanded="false"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/></svg></button>';
    const holder = area.closest('.table-scroll, .overflow-x-auto') || area;
    holder.insertAdjacentElement('afterend',tools);
    const toggle=tools.querySelector('.record-remove-toggle'), cancel=tools.querySelector('.record-remove-cancel'), confirm=tools.querySelector('.record-remove-confirm'), status=tools.querySelector('[role=status]');
    const boxes = [];
    function update() { const count=boxes.filter(x=>x.box.checked).length; status.textContent=count+' selected'; confirm.disabled=!count; }
    function close() { boxes.forEach(x=>{x.box.remove();x.node.classList.remove('record-removal-selected');}); boxes.length=0; status.hidden=cancel.hidden=confirm.hidden=true; toggle.setAttribute('aria-expanded','false'); toggle.focus(); }
    toggle.addEventListener('click',()=>{
      if (boxes.length) { close();return; }
      records.forEach((record,node)=>{
        const box=document.createElement('input'); box.type='checkbox';box.className='record-removal-choice';box.setAttribute('aria-label','Select '+record.kind.replaceAll('_',' ')+' '+record.id+' for removal');
        (node.matches('tr') ? node.querySelector('td') : node)?.prepend(box);
        box.addEventListener('change',()=>{node.classList.toggle('record-removal-selected',box.checked);update();});
        boxes.push({box,node,record});
      });
      status.hidden=cancel.hidden=confirm.hidden=false;toggle.setAttribute('aria-expanded','true');update();boxes[0]?.box.focus();
    });
    cancel.addEventListener('click',close);
    confirm.addEventListener('click',async()=>{
      const selected=boxes.filter(x=>x.box.checked).map(x=>x.record);
      if (!selected.length) return;
      const reason=window.prompt('Reason for removing these records (at least 5 characters):');
      if (reason===null) return;
      if(reason.trim().length<5){status.textContent='A reason of at least 5 characters is required.';return;}
      if(!window.confirm('Remove '+selected.length+' selected record(s) from active use? Files and history will be retained for administrator restoration.'))return;
      confirm.disabled=cancel.disabled=toggle.disabled=true;
      try {
        const token=ei ? document.querySelector('[name=csrfmiddlewaretoken]')?.value : config.dataset.token;
        const response=await fetch(config.dataset.endpoint,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json',[ei?'X-CSRFToken':'X-Record-CSRF']:token||''},body:JSON.stringify({records:selected,reason:reason.trim()})});
        if (!(response.headers.get('Content-Type')||'').includes('application/json')) throw new Error('Removal could not be authorized. Refresh the page and sign in again if needed.');
        const result=await response.json();
        if(!response.ok)throw new Error(result.error||'Removal failed.');
        location.reload();
      }catch(error){status.textContent=error.message;confirm.disabled=cancel.disabled=toggle.disabled=false;}
    });
  });
})();
