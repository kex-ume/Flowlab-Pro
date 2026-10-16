/* E&I job wizard, protected actions and acknowledged server draft recovery. */
(() => {
  'use strict';
  const $ = (s, p = document) => p.querySelector(s);
  const $$ = (s, p = document) => [...p.querySelectorAll(s)];
  const token = () => $('input[name="csrfmiddlewaretoken"]')?.value || document.cookie.split('; ').find(c => /^(ei_qa_|ei_lab_)?csrftoken=/.test(c))?.split('=').slice(1).join('=');
  const node = (tag, text, cls) => { const e = document.createElement(tag); if (text != null) e.textContent = text; if (cls) e.className = cls; return e; };
  function associateLabels(root=document){$$('.ei-action-form label, #ei-template-form label',root).forEach((label,i)=>{if(label.htmlFor)return;const control=label.parentElement.querySelector('input:not([type="hidden"]),select,textarea');if(control){control.id ||= 'ei-control-'+crypto.randomUUID();label.htmlFor=control.id;}});}
  associateLabels();
  async function request(url, data, method = 'POST') {
    const isFile = data instanceof FormData;
    const headers = {'X-CSRFToken': token()};
    if (!isFile) headers['Content-Type'] = 'application/json';
    const response = await fetch(url, {method, headers, credentials: 'same-origin', body: method === 'GET' ? undefined : isFile ? data : JSON.stringify(data || {})});
    const type = response.headers.get('content-type') || '';
    if (!type.includes('application/json')) throw new Error('The server did not return a valid response. Sign in again or retry.');
    const result = await response.json();
    if (!response.ok) { const error = new Error(result.error || 'Request failed.'); error.conflict = response.status === 409; throw error; }
    return result;
  }
  function message(target, text, bad = false) { if (target) { target.textContent = text; target.classList.toggle('ei-error', bad); } }

  $$('.ei-action-form').forEach(form => {
    form.addEventListener('submit', async event => {
      if (event.defaultPrevented) return;
      event.preventDefault();
      if (!form.reportValidity()) return;
      const button = event.submitter || $('button[type="submit"]', form);
      const area = $('.ei-form-message', form);
      button.disabled = true; message(area, 'Saving…');
      try {
        const formData = new FormData(form);
        const hasFile = $$('input[type="file"]', form).some(input => input.files.length > 0);
        const result = await request(form.action, hasFile ? formData : Object.fromEntries(formData));
        message(area, 'Saved.');
        if (button.hasAttribute('data-follow-url') && result.url) location.href = result.url;
        else location.reload();
      } catch (error) { message(area, error.message, true); button.disabled = false; button.classList.remove('opacity-50','cursor-not-allowed'); }
    });
  });
  $$('[data-source-select]').forEach(select => select.addEventListener('change', () => { const area = $('[data-upload-field]', select.form); if (area) { area.hidden = select.value !== 'upload'; $('input', area).required = !area.hidden; } }));
  $$('select[data-record-kind]').forEach(select => { const update = () => { const area = $('[data-calibration-phase]', select.form); if (area) area.hidden = select.value !== 'calibration'; }; select.addEventListener('change', update); update(); });
  $$('[data-personnel-combo]').forEach(input => input.addEventListener('input', () => {
    const options = $$('option', document.getElementById(input.getAttribute('list')));
    const selected = options.find(o => o.value === input.value);
    const hidden = input.parentElement.querySelector('input[type="hidden"]');
    hidden.value = selected?.dataset.id || ''; input.setCustomValidity(selected || !input.value ? '' : 'Select an eligible registered personnel record.');
  }));
  $$('[data-review-decision]').forEach(select => {
    function update() { const form = select.form; const comment = $('[data-decision-comment]', form), assignee = $('[data-decision-assignee]', form); comment.hidden = !['comment', 'revert'].includes(select.value); $('textarea', comment).required = !comment.hidden; assignee.hidden = !['comment', 'another'].includes(select.value); $('input:not([type="hidden"])', assignee).required = !assignee.hidden; }
    select.addEventListener('change', update); update();
  });
  $$('[data-ei-action]').forEach(button => button.addEventListener('click', async () => {
    const data = {};
    if (button.hasAttribute('data-reason')) { data.reason = prompt('Reason / comment for this action:'); if (!data.reason?.trim()) return; }
    button.disabled = true;
    let area = $('#ei-record-error') || node('p', '', 'ei-form-message'); if (!area.parentNode) button.parentElement.append(area);
    try {
      if (button.hasAttribute('data-save-before') && window.eiSaveRecord) await window.eiSaveRecord();
      const result = await request(button.dataset.eiAction, data);
      if (result.url && button.hasAttribute('data-reason') && button.dataset.eiAction.includes('/amend/')) location.href = result.url;
      else location.reload();
    } catch (error) { message(area, error.message, true); button.disabled = false; }
  }));

  const wizardData = $('#ei-job-bootstrap');
  if (wizardData) {
    const config = JSON.parse(wizardData.textContent), panel = $('#new-job-form'), form = $('#ei-job-wizard');
    const trigger = $('#show-new-job'), close = $('#close-new-job');
    let step = 0, saved = config.job || null, creationKey = crypto.randomUUID(), saving = false;
    const initial = config.initial || {};
    const msg = $('#ei-wizard-message');
    function option(select, value, text) { const o = node('option', text); o.value = value; select.append(o); }
    config.clients.forEach(c => option($('#wizard-client'), c.id, c.name));
    config.personnel.forEach(p => { option($('#wizard-assignees'), p.id, p.name); option($('#wizard-primary'), p.id, p.name); if (p.supervisor) option($('#wizard-supervisor'), p.id, p.name); });
    $('#wizard-creator').textContent = config.creator;
    for (const [key, value] of Object.entries(initial)) { const input = form.elements.namedItem(key); if (input && key !== 'assignees') input.value = value ?? ''; }
    $$('#wizard-assignees option').forEach(o => o.selected = (initial.assignees || []).map(String).includes(o.value));
    function field(parent, name, label, value = '', choices = null) {
      const box = node('div'), lab = node('label', label), input = node(choices ? 'select' : 'input');
      input.dataset.field = name; input.id = 'uut-' + crypto.randomUUID(); lab.htmlFor = input.id;
      if (choices) choices.forEach(c => option(input, c[0], c[1]));
      input.value = value ?? ''; box.append(lab, input); parent.append(box); return input;
    }
    function addUUT(row = {}) {
      const item = node('div', null, 'ei-uut-entry'); item.dataset.id = row.id || '';
      const head = node('div', null, 'ei-workspace-heading'); head.append(node('strong', 'Equipment / UUT'));
      const remove = node('button', 'Remove', 'ei-records-view'); remove.type = 'button'; remove.addEventListener('click', () => { if (confirm('Remove this UUT from the draft?')) item.remove(); }); head.append(remove); item.append(head);
      const grid = node('div', null, 'ei-new-job-grid');
      for (const [key, label] of [['name','Equipment name'],['equipment_type','Equipment type'],['manufacturer','Manufacturer'],['model','Model'],['serial_number','Serial number'],['equipment_identifier','Equipment identifier']]) field(grid, key, label, row[key]);
      field(grid, 'request_type', 'Request type', row.request_type || 'calibration', [['calibration','Calibration'],['repair','Repair'],['calibration_repair','Calibration and Repair']]);
      const scope = field(grid, 'scope', 'Calibration scope', row.scope, [['','Select scope'], ...config.scopes.map(s => [s.id,s.name])]);
      const template = field(grid, 'template', 'Approved log template', '', [['','Select template / hand-filled record']]);
      function templates() { template.replaceChildren(); option(template, '', 'Select template / hand-filled record'); config.templates.filter(t => String(t.scope_id) === scope.value).forEach(t => option(template,t.id,t.title+' · v'+t.version)); }
      scope.addEventListener('change', templates); templates(); template.value = row.template || '';
      field(grid, 'duplicate_reason', 'Duplicate serial override reason (only if legitimate)', row.duplicate_reason);
      item.append(grid); $('#ei-uuts-entry').append(item);
    }
    (initial.uuts || []).forEach(addUUT);
    $('#ei-add-uut').addEventListener('click', () => addUUT());
    function collect() {
      const values = Object.fromEntries(new FormData(form));
      delete values.csrfmiddlewaretoken;
      values.creation_key = creationKey;
      values.version = saved?.version ?? 0;
      values.assignees = $$('#wizard-assignees option:checked').map(o => Number(o.value));
      values.uuts = $$('.ei-uut-entry').map(item => { const row = {id: item.dataset.id || undefined}; $$('[data-field]', item).forEach(e => row[e.dataset.field] = e.value); return row; });
      return values;
    }
    function showPage(next) {
      step = Math.max(0,Math.min(3,next)); $$('[data-page]',panel).forEach(p => p.hidden = Number(p.dataset.page) !== step);
      $$('[data-step]',panel).forEach(b => b.setAttribute('aria-selected',String(Number(b.dataset.step) === step)));
      $('#ei-wizard-back').disabled = step === 0; $('#ei-wizard-next').hidden = step === 3; $('#ei-submit-job').hidden = step !== 3;
      $('#ei-submit-job').textContent = 'Submit for Review';
      $('#ei-lab-document-fields').hidden = $('#wizard-type').value === 'field';
      if(step===2) refreshEligible();
      if (step === 3) { const values = collect(); const review = $('#ei-wizard-review'); review.replaceChildren(); review.append(node('h3','Review before submission')); for (const [label,value] of [['Client', config.clients.find(c => String(c.id)===values.client)?.name || 'Not selected'],['Job type', values.job_type],['Equipment / UUTs', values.uuts.length],['Scheduled end',values.end_date || 'Not set'],['Approval action','Supervisor review, then Chief / Administrator approval']]) { const p = node('p'); p.append(node('strong',label+': '),document.createTextNode(value)); review.append(p); } }
    }
    async function refreshEligible(){
      try{
        const result=await request(config.eligible_url,{uuts:collect().uuts});
        for(const id of ['wizard-assignees']){
          const select=document.getElementById(id), values=[...select.selectedOptions].map(o=>o.value);
          select.replaceChildren();if(id==='wizard-primary')option(select,'','Select eligible personnel');
          result.personnel.forEach(p=>option(select,p.id,p.name));
          [...select.options].forEach(o=>o.selected=values.includes(o.value));
        }
      }catch(error){message(msg,error.message,true);}
    }
    function show(open) { panel.hidden = !open; trigger?.setAttribute('aria-expanded',String(open)); if(open) panel.scrollIntoView({behavior:'smooth',block:'start'}); }
    trigger?.addEventListener('click',()=>show(panel.hidden)); close.addEventListener('click',()=>show(false));
    $$('[data-step]',panel).forEach(b=>b.addEventListener('click',()=>showPage(Number(b.dataset.step))));
    $('#ei-wizard-next').addEventListener('click',()=>showPage(step+1)); $('#ei-wizard-back').addEventListener('click',()=>showPage(step-1)); $('#wizard-type').addEventListener('change',()=>showPage(step));
    function docs() { const area = $('#ei-wizard-documents'); area.replaceChildren(); (config.documents || []).forEach(d=> { const link=node('a',d.kind+' · '+d.name,'ei-records-view'); link.href=d.url; link.target='_blank'; link.rel='noopener'; area.append(link); }); }
    async function save(action = null) {
      if (saving) return; saving = true; $$('button',form).forEach(b=>b.disabled=true); message(msg,'Saving…');
      try {
        const url = saved ? config.save_url.replace(/save\/$/,saved.id+'/save/') : config.save_url;
        saved = await request(url,collect());
        saved.snapshot.uuts.forEach((r,i)=>{ if($$('.ei-uut-entry')[i]) $$('.ei-uut-entry')[i].dataset.id=r.id; });
        for (const input of $$('input[type="file"][data-kind]',form)) if(input.files.length && $('#wizard-type').value==='lab') { const data=new FormData(); data.append('file',input.files[0]); data.append('kind',input.dataset.kind); const doc=await request(config.save_url.replace(/save\/$/,saved.id+'/documents/'),data); (config.documents ||= []).push({kind:input.dataset.kind,name:doc.name,url:doc.url}); input.value=''; }
        docs(); message($('#ei-job-save-status'),'Draft saved'); message(msg,'Draft saved in E&I storage.');
        if(action) { await request(config.save_url.replace(/save\/$/,saved.id+'/action/'+action+'/'),{}); location.href=saved.url; }
      } catch(error) { message(msg,error.message,true); }
      finally { saving=false; $$('button',form).forEach(b=>b.disabled=false); showPage(step); }
    }
    $('#ei-save-draft').addEventListener('click',()=>save()); $('#ei-submit-job').addEventListener('click',()=>save('submit'));
    form.addEventListener('submit',e=>e.preventDefault()); docs(); showPage(0);
    const params=new URLSearchParams(location.search); if(params.get('add')==='1'||params.get('edit')==='1') show(true);
  }

  const recordNode = $('#ei-record-bootstrap');
  if (recordNode) {
    const config=JSON.parse(recordNode.textContent), area=$('#ei-digital-record'), state=$('#ei-autosave-status'), errorArea=$('#ei-record-error');
    let data=structuredClone(config.data), version=config.version, dirty=false, saving=false, timer=null, nextSave=false;
    function inputField(parent, f, value, table=null) {
      const wrap=node('div'), label=node('label', f.label || f.name), input=node(f.type==='select'?'select':f.type==='text'?'textarea':'input');
      input.id='record-'+crypto.randomUUID(); label.htmlFor=input.id; input.dataset.field=f.name; if(table) input.dataset.table=table;
      if(f.type==='select') (f.choices||[]).forEach(c=>{const text=f.name==='calibration_phase' ? c==='as_found'?'As Found':'As Left' : c;const o=node('option',text);o.value=c;input.append(o);});
      if(f.type==='number') { input.type='number'; input.step='any'; if(f.min!=null)input.min=f.min; if(f.max!=null)input.max=f.max; }
      if(f.type==='date')input.type='date'; input.value=value ?? ''; input.disabled=!config.editable; wrap.append(label,input); if(f.unit)wrap.append(node('small',f.unit,'ei-muted')); parent.append(wrap);
    }
    function render() {
      area.replaceChildren(); (config.schema.fields||[]).forEach(f=>inputField(area,f,data[f.name]));
      if(config.reference_standards){
        const box=node('div',null,'ei-new-job-wide');const select=node('select');select.multiple=true;select.size=4;select.id='ei-record-standards';select.dataset.references='true';select.disabled=!config.editable;const label=node('label','Reference standards used');label.htmlFor=select.id;
        const options=config.editable?config.reference_standards:(data.reference_standards_snapshot||[]).map(s=>({id:s.id,name:s.name,serial_no:s.serial,certificate_no:s.certificate}));
        options.forEach(s=>{const option=node('option',s.name+' · '+s.serial_no+' · '+(s.certificate_no||'Certificate not recorded'));option.value=s.id;option.selected=(data.reference_standards||[]).map(String).includes(String(s.id));select.append(option);});box.append(label,select);area.append(box);
      }
      (config.schema.tables||[]).forEach(table=>{const section=node('section',null,'ei-new-job-wide ei-record-table'); section.dataset.tableName=table.name; section.append(node('h3',table.label||table.name)); const rows=node('div'); section.append(rows);
        function addRow(row={}) { const grid=node('div',null,'ei-record-row ei-new-job-grid'); table.columns.forEach(f=>inputField(grid,f,row[f.name],table.name)); if(config.editable){const remove=node('button','Remove Row','ei-records-view');remove.type='button';remove.addEventListener('click',()=>{grid.remove();changed();});grid.append(remove);} rows.append(grid); }
        (data[table.name]||[]).forEach(addRow); if(config.editable){const button=node('button','Add Row','ei-records-view');button.type='button';button.addEventListener('click',()=>{addRow();changed();});section.append(button);} area.append(section);
      });
      if(!config.editable && !config.schema.fields?.length) Object.entries(data).forEach(([key,value])=>{const box=node('div');box.append(node('label',key.replaceAll('_',' ')),node('p',typeof value==='object'?JSON.stringify(value):value));area.append(box);});
    }
    function collect() { const values={}; $$('[data-field]:not([data-table])',area).forEach(e=>values[e.dataset.field]=e.value); if($('[data-references]',area))values.reference_standards=$$('[data-references] option:checked',area).map(o=>Number(o.value)); $$('[data-table-name]',area).forEach(t=>values[t.dataset.tableName]=$$('.ei-record-row',t).map(row=>Object.fromEntries($$('[data-field]',row).map(e=>[e.dataset.field,e.value])))); return values; }
    function changed() { if(!config.editable)return;dirty=true;message(state,'Unsaved changes');clearTimeout(timer);timer=setTimeout(()=>save().catch(()=>{}),700); }
    async function save() {
      if(!config.editable||!dirty)return;
      if(saving){nextSave=true;return new Promise((resolve,reject)=>{const interval=setInterval(()=>{if(!saving){clearInterval(interval);save().then(resolve,reject);}},50);});}
      saving=true;const values=collect();message(state,'Saving…');
      try { const result=await request(config.save_url,{data:values,version});version=result.version;data=result.data;dirty=JSON.stringify(collect())!==JSON.stringify(values);message(state,'Saved at '+result.saved_at);message(errorArea,''); }
      catch(error){dirty=true;message(state,error.conflict?'Revision conflict':'Offline / Retry',true);message(errorArea,error.message,true);$('#ei-conflict').hidden=!error.conflict;throw error;}
      finally {saving=false;if(nextSave){nextSave=false;save().catch(()=>{});}}
    }
    window.eiSaveRecord=save; render();message(state,'Saved at '+config.saved_at);
    area.addEventListener('input',changed);area.addEventListener('change',changed);$('#ei-save-record')?.addEventListener('click',()=>save().catch(()=>{}));
    setInterval(()=>{if(dirty&&!saving&&$('#ei-conflict').hidden)save().catch(()=>{});},15000);
    window.addEventListener('beforeunload',event=>{if(dirty||saving){event.preventDefault();event.returnValue='';}});
    $('#ei-reload-draft').addEventListener('click',async()=>{if(!confirm('Replace displayed inputs with the latest acknowledged server draft?'))return;try{const latest=await request(config.save_url,null,'GET');data=latest.data;version=latest.version;dirty=false;render();$('#ei-conflict').hidden=true;message(state,'Saved at '+latest.saved_at);}catch(error){message(errorArea,error.message,true);}});
    $('#ei-reconcile-draft').addEventListener('click',async()=>{if(!confirm('Save your displayed inputs as the next revision after the latest server save?'))return;try{const latest=await request(config.save_url,null,'GET');version=latest.version;$('#ei-conflict').hidden=true;await save();}catch(error){message(errorArea,error.message,true);}});
  }

  const templateForm=$('#ei-template-form');
  if(templateForm){
    function addField(){const row=node('div',null,'ei-template-field ei-new-job-grid');for(const [name,label] of [['name','Field identifier'],['label','Label'],['unit','Unit'],['precision','Decimal precision'],['choices','Select choices (comma separated)']]){const box=node('div');const input=node('input');input.dataset.schema=name;box.append(node('label',label),input);row.append(box);}const type=node('select');type.dataset.schema='type';['number','text','date','select'].forEach(v=>{const o=node('option',v);o.value=v;type.append(o);});const box=node('div');box.append(node('label','Field type'),type);row.append(box);const required=node('input');required.type='checkbox';required.dataset.schema='required';const req=node('label','Required ');req.append(required);row.append(req);const remove=node('button','Remove Field','ei-records-view');remove.type='button';remove.addEventListener('click',()=>row.remove());row.append(remove);$('#ei-template-fields').append(row);}
    $('#ei-add-template-field').addEventListener('click',()=>{addField();associateLabels();});
    templateForm.addEventListener('submit',async event=>{event.preventDefault();if(!templateForm.reportValidity())return;const msg=$('.ei-form-message',templateForm);try{const advanced=JSON.parse(templateForm.elements.advanced.value||'{}');advanced.fields=$$('.ei-template-field').map(row=>Object.fromEntries($$('[data-schema]',row).map(e=>[e.dataset.schema,e.type==='checkbox'?e.checked:e.dataset.schema==='choices'?e.value.split(',').map(x=>x.trim()).filter(Boolean):e.dataset.schema==='precision'?e.value===''?undefined:Number(e.value):e.value])));advanced.allow_upload=templateForm.elements.allow_upload.value==='true';advanced.method_reference=templateForm.elements.method_reference.value;await request(templateForm.action,{title:templateForm.elements.title.value,schema:advanced});location.reload();}catch(error){message(msg,error.message,true);}finally{const submit=templateForm.querySelector('button[type="submit"]');submit.disabled=false;submit.classList.remove('opacity-50','cursor-not-allowed');}});
  }
})();
