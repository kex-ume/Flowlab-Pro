(() => {
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const value = id => $(id).value;
  const number = raw => raw === '' || raw == null ? null : Number(raw);
  const format = raw => {if(!Number.isFinite(Number(raw)))return '—';const text=Number(raw).toPrecision(6);return /e/i.test(text)?text:text.replace(/\.?0+$/,'');};
  const clone = object => JSON.parse(JSON.stringify(object));
  const config = window.FLOWLAB_GUM || {sourceTemplates:{},cmcRecords:[]};

  function blankPoint() {
    return {label:'',nominalFlow:'',flowUnit:'',densityUnit:'m³/kg',refTemp:'',refPressure:'',runs:[],sources:[],correlations:[],coverageMode:'auto',manualK:'',coverageProb:95,cmcExpression:'',cmcA:'',cmcB:'',backendResult:null,observationPreview:null};
  }
  function newCalculationId() {
    const stamp=new Date().toISOString().slice(0,10).replaceAll('-','');
    const bytes=new Uint8Array(2); crypto.getRandomValues(bytes);
    return `UB-${stamp}-${[...bytes].map(item=>item.toString(16).padStart(2,'0')).join('').toUpperCase()}`;
  }
  function initialState() {
    return {recordId:null,calculationId:newCalculationId(),revision:0,status:'Draft',calculationType:'mutGrav',jobId:'',jobNumber:'',jobStatus:'',projectNumber:'',projectName:'',customer:'',mut:'',mutAssetId:'',serialNumber:'',manufacturer:'',model:'',meterType:'',rangeMin:'',rangeMax:'',rangeUnit:'',flowPointCount:1,jobMethod:'',analyst:value('#analyst'),calcDate:new Date().toISOString().slice(0,10),fluid:'',quantity:'mass',points:[blankPoint()],activePoint:0,isCmc:false,cmcComparison:[]};
  }
  let state = initialState();
  state.standalone=$('#gumApp').dataset.standalone==='1';
  let equipmentSourceIndex = null;
  let draftDirty = false, draftTimer = null;

  function currentPoint() { return state.points[state.activePoint]; }
  const volumeFlowUnits=new Set(['m³/s','m³/h','L/s','L/min','BPD']);
  const massFlowUnits=new Set(['kg/s','kg/min','kg/h','g/s','g/min']);
  function effectiveQuantity() {
    const unit=currentPoint()?.flowUnit||state.rangeUnit||'';
    if(volumeFlowUnits.has(unit))return 'volume';
    if(massFlowUnits.has(unit))return 'mass';
    return String(state.quantity||'').toLowerCase().includes('volume')?'volume':'mass';
  }
  function syncMeta() {
    state.jobId=value('#jobId'); state.analyst=value('#analyst'); state.calcDate=value('#calcDate');
    state.fluid=value('#fluid'); state.quantity=value('#quantity'); state.customer=value('#customer');
    state.mut=value('#mut'); state.mutAssetId=value('#mutAssetId'); state.serialNumber=value('#serialNumber');
    state.manufacturer=value('#manufacturer'); state.model=value('#model'); state.meterType=value('#meterType');
    state.jobMethod=value('#jobMethod');
    const option=$('#jobId').selectedOptions[0]; state.jobNumber=option?.dataset.number || '';
  }
  function syncPoint() {
    const point=currentPoint();
    Object.assign(point,{label:value('#pointLabel'),nominalFlow:value('#nominalFlow'),flowUnit:value('#flowUnit'),densityUnit:value('#densityUnit'),refTemp:value('#refTemp'),refPressure:value('#refPressure'),coverageMode:value('#coverageMode'),manualK:value('#manualK'),coverageProb:value('#coverageProb'),cmcExpression:value('#cmcExpression'),cmcA:value('#cmcA'),cmcB:value('#cmcB')});
  }
  function payload(points=state.points) { syncMeta(); syncPoint(); return {...state,points:clone(points)}; }
  function setMessage(message, kind='') { $('#validationSummary').textContent=message; $('#validationSummary').className=kind; }
  function canAutoSave() { return $('#gumApp').dataset.canSave==='1'&&['Draft','Reverted'].includes(state.status)&&(state.isCmc||state.jobId); }
  function markDraftDirty(event) {
    if(event?.target?.closest('#reviewAssignmentModal'))return;
    draftDirty=true;clearTimeout(draftTimer);if(canAutoSave())draftTimer=setTimeout(()=>autosaveDraft(true),900);
  }
  async function autosaveDraft(showMessage=false) {
    if(!draftDirty||!canAutoSave())return null;
    try{
      const body=await requestJson('/uncertainty/api/autosave',{method:'POST',body:JSON.stringify(payload())});
      if(body.record.existing&&!state.recordId){draftDirty=false;await loadRecord(body.record.isCmc?'cmc':'calculation',body.record.id);setMessage('The existing Draft for this Job and method was restored.');return body.record;}
      Object.assign(state,{recordId:body.record.id,calculationId:body.record.calculationId,revision:body.record.revision,status:body.record.status,createdBy:body.record.createdBy||state.createdBy,isCmc:body.record.isCmc||state.isCmc});
      draftDirty=false;$('#recordIdPill').textContent=state.calculationId;$('#statusPill').textContent=state.status.toUpperCase();renderWorkflowActions();
      if(showMessage)setMessage('Draft saved automatically to FlowLab Pro.');
      return body.record;
    }catch(error){if(showMessage)setMessage(error.message,'validation-error');return null;}
  }
  async function discardDraft() {
    if(!state.recordId||!confirm('Discard this Draft and remove its in-progress data?'))return;
    try{const type=state.isCmc?'cmc':'calculation';await requestJson(`/uncertainty/api/records/${type}/${state.recordId}/discard`,{method:'POST',body:'{}'});draftDirty=false;state=initialState();state.standalone=$('#gumApp').dataset.standalone==='1';renderAll();setMessage('Draft discarded.');}catch(error){setMessage(error.message,'validation-error');}
  }

  function renderMeta() {
    $('#calcId').value=state.calculationId; $('#jobId').value=state.jobId; $('#analyst').value=state.analyst;
    $('#customer').value=state.customer; $('#calcDate').value=state.calcDate; $('#project').value=[state.projectNumber,state.projectName].filter(Boolean).join(' · '); $('#mut').value=state.mut;
    $('#mutAssetId').value=state.mutAssetId; $('#serialNumber').value=state.serialNumber; $('#manufacturer').value=state.manufacturer;
    $('#model').value=state.model; $('#meterType').value=state.meterType; $('#jobRange').value=(state.rangeMin!==''&&state.rangeMin!=null)?`${state.rangeMin}–${state.rangeMax} ${state.rangeUnit}`:'';
    $('#jobMethod').value=state.jobMethod; $('#fluid').value=state.fluid; $('#quantity').value=state.quantity;
    $('#recordIdPill').textContent=state.calculationId || 'New calculation'; $('#statusPill').textContent=state.status.toUpperCase();
    $('#statusPill').className=`gum-pill ${state.status.toLowerCase().replaceAll(' ','-')}`;
    const editable=['Draft','Reverted'].includes(state.status);
    $('#gumApp').classList.toggle('locked',!editable); $('#saveBtn').disabled=!editable || $('#gumApp').dataset.canSave!=='1';
    renderWorkflowActions();
  }
  function renderWorkflowActions() {
    const host=$('#workflowActions'), canSave=$('#gumApp').dataset.canSave==='1';
    const canReview=$('#gumApp').dataset.canReview==='1', canApprove=$('#gumApp').dataset.canApprove==='1';
    const actor=$('#gumApp').dataset.currentActor, isCreator=actor&&actor===state.createdBy;
    const isTechnicalReviewer=actor&&actor===state.reviewedBy;
    let controls='';
    const chief=$('#gumApp').dataset.currentRole==='Chief Meteorologist';
    if(state.recordId&&['Draft','Reverted'].includes(state.status)&&canSave)controls=`<button type="button" class="gum-btn" data-workflow="submit">${chief?'Submit and Approve':'Assign and Submit for Review'}</button><button type="button" class="gum-btn secondary" data-discard-draft>Discard Draft</button>`;
    else if(state.status==='Submitted for Review'&&canReview&&!isCreator)controls='<button type="button" class="gum-btn" data-workflow="review">Complete Technical Review</button><button type="button" class="gum-btn secondary" data-workflow="revert">Revert</button>';
    else if(state.status==='Submitted for Review')controls='<small>Awaiting technical review</small>';
    else if(state.status==='HOD Review'&&canApprove&&!isCreator&&!isTechnicalReviewer)controls='<button type="button" class="gum-btn" data-workflow="approve">Approve</button><button type="button" class="gum-btn secondary" data-workflow="revert">Revert</button>';
    else if(state.status==='HOD Review')controls='<small>Awaiting Chief/Supervisor approval</small>';
    host.innerHTML=controls;
  }
  function renderContext() {
    $$('#contextbar [data-context]').forEach(button => button.classList.toggle('active',button.dataset.context===state.calculationType));
    const coriolis=state.calculationType.endsWith('Cor'), cmc=state.calculationType.startsWith('cmc');
    const modelInfo=$('#modelInfo');
    const densityBasis=currentPoint().densityUnit==='m³/kg'?'specific volume: q = (m × v)/t':'density: q = m/(ρt)',quantity=effectiveQuantity();
    modelInfo.dataset.info=coriolis?'Corrected master reference: meter factor or K-factor uses qMM = qIndication × factor; a correction value uses qMM = qIndication × (1 + correction). Relative error: E = ((MUT − qMM)/qMM) × 100.':(quantity==='volume'?`Volumetric reference using ${densityBasis}. The base m³/s result is converted into the selected flow unit before relative error is evaluated.`:'Mass reference flow: q = m/t. The base kg/s result is converted into the selected mass-flow unit before relative error is evaluated. Density is excluded.');
    $('#formulaBox').textContent=coriolis?'Uses the corrected indication of the selected approved master meter as the reference for every observation.':(quantity==='volume'?'Uses retained mass, collection time and density to determine volumetric reference flow.':'Uses retained mass and collection time to determine mass reference flow.');
    $('#evaluationBadge').textContent=cmc?'LABORATORY CMC':'MUT CALIBRATION';
    $$('.cmc-field').forEach(element=>element.hidden=!cmc); state.isCmc=cmc;
    renderPoints(); renderRuns(); renderSources(); renderCorrelations(); renderResult();
  }
  function renderPoints() {
    const jobControlsPoints=!state.isCmc&&!!state.jobId;
    $('#pointbar').innerHTML=state.points.map((point,index)=>`<button type="button" class="${index===state.activePoint?'active':''}" data-point="${index}">${esc(point.label || (point.nominalFlow?`${point.nominalFlow} ${point.flowUnit}`:`Point ${index+1}`))}${state.points.length>1&&state.status!=='Approved'&&!jobControlsPoints?`<span class="delete-point" data-delete-point="${index}">×</span>`:''}</button>`).join('');
    const point=currentPoint(); $('#pointLabel').value=point.label; $('#nominalFlow').value=point.nominalFlow; $('#flowUnit').value=point.flowUnit;
    $('#flowUnit').disabled=jobControlsPoints; $('#densityUnit').value=point.densityUnit||'kg/m³'; $('#densityUnitField').hidden=effectiveQuantity()!=='volume'||state.calculationType.endsWith('Cor');
    $('#addPointBtn').disabled=jobControlsPoints; $('#duplicatePointBtn').disabled=jobControlsPoints;
    $('#refTemp').value=point.refTemp; $('#refPressure').value=point.refPressure; $('#coverageMode').value=point.coverageMode;
    $('#manualK').value=point.manualK; $('#coverageProb').value=point.coverageProb; $('#cmcExpression').value=point.cmcExpression;
    $('#cmcA').value=point.cmcA; $('#cmcB').value=point.cmcB;
  }
  function renderRuns() {
    const coriolis=state.calculationType.endsWith('Cor'),quantity=effectiveQuantity(),flowUnit=currentPoint().flowUnit||state.rangeUnit||'';
    refreshObservationPreview();
    const mutHeading=`MUT indication${flowUnit?` (${flowUnit})`:''}`,mutPrompt=flowUnit?`Required · ${flowUnit}`:'Required · select flow unit';
    const headers=coriolis?['Run','Master meter','Master indication','Correction / factor','Correction basis',mutHeading,'Reference flow','Error (%)','']:['Run','Collected mass (kg)','Collection time (s)','Density / specific volume',mutHeading,'Reference flow','Error (%)',''];
    const rows=currentPoint().runs.map((run,index)=>{const evaluated=currentPoint().backendResult?.observations?.[index]||currentPoint().observationPreview?.observations?.[index]||evaluateRun(run)||run;return `<tr data-run="${index}"><td>${index+1}</td>${coriolis?`<td><button type="button" data-master-equipment="${index}">${esc(run.masterEquipmentLabel||'Select Equipment')}</button></td><td><input data-run-key="master" type="number" step="any" value="${esc(run.master)}"></td><td><input data-run-key="correction" type="number" step="any" value="${esc(run.correction)}"></td><td><select data-run-key="correctionBasis">${options([['','Select basis'],['curve','Correction curve'],['factor','Meter factor'],['certificate','Calibration certificate'],['k-factor','K-factor'],['equation','Approved correction equation']],run.correctionBasis)}</select></td><td><input data-run-key="mut" type="number" step="any" value="${esc(run.mut)}" placeholder="${esc(mutPrompt)}" title="Enter the MUT flow-rate indication in ${esc(flowUnit||'the selected flow unit')}."></td>`:`<td><input data-run-key="mass" type="number" step="any" value="${esc(run.mass)}"></td><td><input data-run-key="time" type="number" step="any" value="${esc(run.time)}"></td><td><input data-run-key="density" type="number" step="any" value="${esc(run.density)}" ${quantity==='mass'?'disabled':''}></td><td><input data-run-key="mut" type="number" step="any" value="${esc(run.mut)}" placeholder="${esc(mutPrompt)}" title="Enter the MUT flow-rate indication in ${esc(flowUnit||'the selected flow unit')}."></td>`}<td data-reference-output>${format(evaluated.reference_flow)}</td><td data-error-output>${format(evaluated.error_percent)}</td><td><button type="button" data-delete-run="${index}" aria-label="Delete observation">×</button></td></tr>`;}).join('');
    $('#runTable').innerHTML=`<thead><tr>${headers.map(item=>`<th>${item==='Density / specific volume'?`Density / specific volume <button class="info-tip" type="button" data-info="The selected point controls whether the input is density in kg/m³ or specific volume in m³/kg. It is applied only to volume flow and the reference is converted into the selected flow unit.">ⓘ</button>`:item}</th>`).join('')}</tr></thead><tbody>${rows||`<tr><td class="empty" colspan="${headers.length}">No observations entered.</td></tr>`}</tbody>`;
    renderTypeAStats();
  }
  function renderTypeAStats() {
    const stats=(currentPoint().backendResult||currentPoint().observationPreview||{}).statistics;
    const validObservations=currentPoint().runs.map(evaluateRun).filter(Boolean).length;
    const items=stats?[['Valid observations',stats.n],['Mean',`${format(stats.mean)} %`],['Sample s',`${format(stats.standard_deviation)} %`],['Calibration repeatability uA',`${format(stats.standard_uncertainty)} %`],['Degrees of freedom',stats.n-1],['Evaluation','Calculated']]:[['Valid observations',validObservations],['Mean','— %'],['Sample s','— %'],['Calibration repeatability uA','— %'],['Degrees of freedom','—'],['Evaluation',validObservations>=2?'Ready to calculate':'Need ≥ 2']];
    $('#typeAStats').innerHTML=items.map(item=>`<article><small>${item[0]}</small><b>${item[1]}</b></article>`).join('');
  }
  function evaluateRun(run) {
    const valid=value=>value!==''&&value!=null&&Number.isFinite(Number(value));
    if(state.calculationType.endsWith('Cor')){
      if(!valid(run.master)||!valid(run.correction)||!valid(run.mut))return null;
      const basis=String(run.correctionBasis||'').toLowerCase();
      const reference=Number(run.master)*(basis==='factor'||basis==='k-factor'?Number(run.correction):1+Number(run.correction));
      return reference<=0?null:{...run,reference_flow:reference,error_percent:(Number(run.mut)-reference)/reference*100};
    }
    if(!valid(run.mass)||!valid(run.time)||!valid(run.mut)||Number(run.mass)<=0||Number(run.time)<=0)return null;
    const quantity=effectiveQuantity();
    if(quantity==='volume'&&(!valid(run.density)||Number(run.density)<=0))return null;
    let reference;
    if(quantity==='volume'){
      const base=currentPoint().densityUnit==='m³/kg'?Number(run.mass)*Number(run.density)/Number(run.time):Number(run.mass)/(Number(run.density)*Number(run.time));
      const factors={'m³/s':1,'m³/h':3600,'L/s':1000,'L/min':60000,'BPD':86400/0.158987294928};
      if(!factors[currentPoint().flowUnit])return null;
      reference=base*factors[currentPoint().flowUnit];
    }else{
      const factors={'kg/s':1,'kg/min':60,'kg/h':3600,'g/s':1000,'g/min':60000};
      if(!factors[currentPoint().flowUnit])return null;
      reference=Number(run.mass)/Number(run.time)*factors[currentPoint().flowUnit];
    }
    return {...run,reference_flow:reference,error_percent:(Number(run.mut)-reference)/reference*100};
  }
  function refreshObservationPreview() {
    const observations=currentPoint().runs.map(evaluateRun);
    if(!observations.length||observations.some(item=>!item)){currentPoint().observationPreview=null;return;}
    const errors=observations.map(item=>item.error_percent),n=errors.length,mean=errors.reduce((sum,item)=>sum+item,0)/n;
    const standardDeviation=n>1?Math.sqrt(errors.reduce((sum,item)=>sum+(item-mean)**2,0)/(n-1)):null;
    const diagnostic=(quantity,key,unit)=>{const values=observations.map(item=>Number(item[key])).filter(Number.isFinite);if(!values.length)return null;const average=values.reduce((sum,item)=>sum+item,0)/values.length;const sample=values.length>1?Math.sqrt(values.reduce((sum,item)=>sum+(item-average)**2,0)/(values.length-1)):null;const uncertainty=sample==null?null:sample/Math.sqrt(values.length);return {quantity,unit,n:values.length,mean:average,standard_deviation:sample,standard_uncertainty:uncertainty,relative_standard_uncertainty:uncertainty!=null&&average!==0?Math.abs(uncertainty/average)*100:null,treatment:key==='error_percent'?'Included as the Type A budget source':'Diagnostic only — captured in result repeatability'};};
    const unit=currentPoint().flowUnit||state.rangeUnit||'',fields=state.calculationType.endsWith('Cor')?[['Master indication','master',unit],['Master correction','correction','fraction']]:[['Collected mass','mass','kg'],['Collection time','time','s'],...(effectiveQuantity()==='volume'?[['Density / specific volume','density',currentPoint().densityUnit||'kg/m³']]:[])];
    const repeatabilityDiagnostics=[...fields,['Reference flow','reference_flow',unit],['MUT indication','mut',unit],['Calibration error','error_percent','%']].map(item=>diagnostic(...item)).filter(Boolean);
    currentPoint().observationPreview={observations,repeatabilityDiagnostics,statistics:n>1?{n,mean,standard_deviation:standardDeviation,standard_uncertainty:standardDeviation/Math.sqrt(n)}:null};
  }
  function options(items,selected) { return items.map(([key,label])=>`<option value="${key}" ${String(key)===String(selected)?'selected':''}>${label}</option>`).join(''); }
  function blankSource(name='') { return {included:true,name,sourceType:'B',value:'',unit:'',basis:'',distribution:'',certK:'',sensitivity:'',dof:'',evidence:'',equipmentId:'',equipmentLabel:'',equipmentProperty:'calibration_uncertainty',notes:''}; }
  function renderSources() {
    const rows=currentPoint().sources.map((source,index)=>`<tr data-source="${index}"><td><input data-source-key="included" type="checkbox" ${source.included?'checked':''}></td><td><input data-source-key="name" value="${esc(source.name)}"></td><td><select data-source-key="sourceType">${options([['B','B'],['A','A']],source.sourceType)}</select></td><td><input data-source-key="value" type="number" step="any" value="${esc(source.value)}" ${source.equipmentId&&source.equipmentProperty!=='other'?'readonly':''}></td><td><input data-source-key="unit" value="${esc(source.unit)}"></td><td><select data-source-key="basis">${options([['','Select basis'],['standard','Standard uncertainty'],['expanded','Expanded uncertainty'],['limit','Distribution limit'],['resolution','Resolution']],source.basis)}</select></td><td><select data-source-key="distribution">${options([['','Select distribution'],['rectangular','Rectangular'],['triangular','Triangular'],['u-shaped','U-shaped']],source.distribution)}</select></td><td><input data-source-key="certK" type="number" step="any" value="${esc(source.certK)}"></td><td>Server</td><td>Server</td><td><input data-source-key="sensitivity" type="number" step="any" value="${esc(source.sensitivity)}"></td><td>Server</td><td><input data-source-key="dof" type="number" step="any" value="${esc(source.dof)}"></td><td><input data-source-key="evidence" value="${esc(source.evidence)}"></td><td><button type="button" data-equipment="${index}">${esc(source.equipmentLabel||'Select Equipment')}</button><select data-source-key="equipmentProperty">${options([['calibration_uncertainty','Calibration uncertainty'],['resolution','Resolution'],['accuracy','Accuracy'],['tolerance','Tolerance'],['drift','Drift / stability'],['other','Other']],source.equipmentProperty)}</select></td><td><button type="button" data-delete-source="${index}" aria-label="Delete source">×</button></td></tr>`).join('');
    $('#sourceTable').innerHTML=`<thead><tr><th>Include?</th><th>Source</th><th>Type A/B</th><th>Input value</th><th>Unit</th><th>Evaluation basis</th><th>Distribution</th><th>Certificate k</th><th>Divisor</th><th>Standard u</th><th>Sensitivity coefficient</th><th>Contribution</th><th>DOF</th><th>Evidence</th><th>Equipment reference</th><th></th></tr></thead><tbody>${rows||'<tr><td colspan="16" class="empty">No uncertainty sources.</td></tr>'}</tbody>`;
  }
  function renderCorrelations() {
    const names=currentPoint().sources.filter(source=>source.included&&source.name).map(source=>[source.name,source.name]);
    const rows=currentPoint().correlations.map((correlation,index)=>`<tr data-correlation="${index}"><td><select data-correlation-key="source_i">${options([['','Select source'],...names],correlation.source_i)}</select></td><td><select data-correlation-key="source_j">${options([['','Select source'],...names],correlation.source_j)}</select></td><td><input data-correlation-key="coefficient" type="number" min="-1" max="1" step="any" value="${esc(correlation.coefficient)}"></td><td><input data-correlation-key="justification" value="${esc(correlation.justification)}"></td><td><button type="button" data-delete-correlation="${index}" aria-label="Delete correlation">×</button></td></tr>`).join('');
    $('#correlationTable').innerHTML=`<thead><tr><th>Source i</th><th>Source j</th><th>Correlation coefficient r</th><th>Justification</th><th></th></tr></thead><tbody>${rows||'<tr><td colspan="5" class="empty">No correlation pairs defined. Sources are treated as independent.</td></tr>'}</tbody>`;
  }
  function renderResult() {
    const point=currentPoint(), calculated=point.backendResult;
    if(!calculated){$('#resultArea').innerHTML='';return;}
    const result=calculated.result;
    const rows=result.components.map(component=>`<tr><td>${esc(component.input.source)}</td><td>${component.input.source_type}</td><td>${format(component.standard_uncertainty)}</td><td>${format(component.input.sensitivity_coefficient)}</td><td>${format(component.contribution)}</td><td>${format(component.contribution_percent)}%</td></tr>`).join('');
    $('#resultArea').innerHTML=`<section class="gum-card result-card"><div class="gum-cardhead"><h3>${esc(point.label||`Flow point ${state.activePoint+1}`)} result</h3><span>GREEN · COMPLETE</span></div><div class="gum-cardbody"><div class="result-grid"><article><small>Combined standard u</small><b>${format(result.combined_standard_uncertainty)} %</b></article><article><small>Covariance sum</small><b>${format(result.covariance_sum)}</b></article><article><small>νeff</small><b>${format(result.effective_degrees_of_freedom)}</b></article><article><small>Coverage factor</small><b>${format(result.coverage_factor)}</b></article><article><small>Expanded uncertainty</small><b>${format(result.expanded_uncertainty)} %</b></article><article><small>Coverage</small><b>${format(result.coverage_probability)}%</b></article></div><div class="gum-table"><table><thead><tr><th>Source</th><th>Type</th><th>Standard u</th><th>Sensitivity</th><th>Contribution</th><th>Contribution %</th></tr></thead><tbody>${rows}</tbody></table></div></div></section>`;
  }
  function renderComparison() {
    const mutType=state.calculationType.startsWith('mut')?state.calculationType:null;
    if(!mutType||!state.points.some(point=>point.backendResult)){ $('#comparisonBody').innerHTML='<div class="empty">Calculate or open a MUT uncertainty record to compare it with an approved CMC.</div>'; return; }
    if(state.cmcComparison?.length){const rows=state.cmcComparison.map(item=>`<tr><td>${format(item.flowPoint)} ${esc(item.flowUnit)}</td><td>${format(item.mutUncertainty)}%</td><td>${format(item.applicableCmc)}%</td><td>${format(item.reportableUncertainty)}%</td><td>${esc(item.status)}</td></tr>`).join('');$('#comparisonBody').innerHTML=`<div class="gum-table"><table><thead><tr><th>Flow point</th><th>Calculated MUT uncertainty</th><th>Applicable CMC</th><th>Reportable uncertainty</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>`;return;}
    const method=mutType==='mutGrav'?'Gravimetric Method':'Coriolis Comparison Method';
    const cmc=config.cmcRecords.find(record=>record.status==='Approved'&&record.method===method);
    if(!cmc){$('#comparisonBody').innerHTML=`<div class="validation-warning">No approved ${esc(method)} CMC budget is available.</div>`;return;}
    const cmcResult=cmc.snapshot.backendResult;
    const rows=state.points.filter(point=>point.backendResult).map(point=>{const mut=point.backendResult.result.expanded_uncertainty;const match=cmcResult.points.find(item=>Number(item.nominalFlow)===Number(point.nominalFlow));const applicable=match?.result.expanded_uncertainty;const reportable=Number.isFinite(applicable)?Math.max(mut,applicable):null;const below=Number.isFinite(applicable)&&mut<applicable;return `<tr><td>${esc(point.label||point.nominalFlow)}</td><td>${format(mut)}%</td><td>${format(applicable)}%</td><td>${format(reportable)}%</td><td>${below?'Calculated uncertainty is below the laboratory CMC — review required.':(applicable==null?'No applicable CMC point':'Complete')}</td></tr>`;}).join('');
    $('#comparisonBody').innerHTML=`<div class="gum-table"><table><thead><tr><th>Flow point</th><th>Calculated MUT uncertainty</th><th>Applicable CMC</th><th>Reportable uncertainty</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }
  function renderAll(){renderMeta();renderContext();renderComparison();}

  async function requestJson(url,options={}) { const response=await fetch(url,{headers:{'Content-Type':'application/json'},...options}); const body=await response.json(); if(!response.ok||!body.ok)throw new Error(body.error||'Request failed.'); return body; }
  async function calculate(points=state.points,pointOnly=false){try{setMessage('Calculating and validating on the server…');const calculationPayload=payload(points);calculationPayload.pointOnly=pointOnly;const body=await requestJson('/uncertainty/api/calculate',{method:'POST',body:JSON.stringify(calculationPayload)});if(pointOnly){currentPoint().backendResult=body.result.points[0];}else{body.result.points.forEach((result,index)=>state.points[index].backendResult=result);state.cmcComparison=body.result.cmcComparison||[];}setMessage('Calculation complete.','');renderRuns();renderResult();renderComparison();return body.result;}catch(error){setMessage(error.message,'validation-error');throw error;}}
  async function save(){if($('#gumApp').dataset.canSave!=='1')return;try{setMessage('Validating and saving the controlled record…');const body=await requestJson('/uncertainty/api/save',{method:'POST',body:JSON.stringify(payload())});body.result.points.forEach((result,index)=>state.points[index].backendResult=result);Object.assign(state,{recordId:body.record.id,calculationId:body.record.calculationId,revision:body.record.revision,status:body.record.status,createdBy:state.createdBy||$('#gumApp').dataset.currentActor,isCmc:body.record.isCmc||false,cmcComparison:body.result.cmcComparison||[]});draftDirty=false;setMessage('Draft saved to the FlowLab Pro database.','');renderAll();}catch(error){setMessage(error.message,'validation-error');}}
  async function loadRecord(type,id){try{const body=await requestJson(`/uncertainty/api/records/${type}/${id}`);const saved=body.record,backend=saved.backendResult;delete saved.backendResult;state={...initialState(),...saved,recordId:saved.recordId,calculationId:saved.calculationId||(type==='cmc'?`CMC revision ${saved.revision}`:''),isCmc:type==='cmc'};state.points=state.points?.length?state.points:[blankPoint()];state.activePoint=0;(backend?.points||[]).forEach((result,index)=>{if(state.points[index])state.points[index].backendResult=result;});state.cmcComparison=backend?.cmcComparison||[];draftDirty=false;navigate('calculator');renderAll();}catch(error){setMessage(error.message,'validation-error');}}
  async function workflowAction(action,assignment=null){
    const chief=$('#gumApp').dataset.currentRole==='Chief Meteorologist';
    if(action==='submit'&&!assignment){await autosaveDraft();if(!chief){const actor=$('#gumApp').dataset.currentActor;$$('#technicalReviewer option,#finalApprover option').forEach(option=>{if(option.value)option.disabled=option.dataset.name===actor;});$('#reviewAssignmentModal').hidden=false;return;}}
    let comment='';if(action==='revert'){comment=window.prompt('Enter the technical reason for reverting this calculation:')||'';if(!comment)return;}
    try{const type=state.isCmc?'cmc':'calculation';const body=await requestJson(`/uncertainty/api/records/${type}/${state.recordId}/workflow`,{method:'POST',body:JSON.stringify({action,comment,...(assignment||{})})});state.status=body.status;if(assignment){state.assignedReviewer=$('#technicalReviewer').selectedOptions[0]?.dataset.name;state.assignedApprover=$('#finalApprover').selectedOptions[0]?.dataset.name;$('#reviewAssignmentModal').hidden=true;}const row=document.querySelector(`[data-load-record="${state.recordId}"]`)?.closest('[data-record-row]');if(row){row.dataset.status=body.status;const status=row.querySelector('.status');if(status){status.textContent=body.status;status.className=`status ${body.status.toLowerCase().replaceAll(' ','-')}`;}}renderAll();setMessage(`Calculation status changed to ${body.status}.`);}catch(error){setMessage(error.message,'validation-error');}
  }
  function navigate(view){$$('[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===view));$$('[data-view-panel]').forEach(panel=>panel.hidden=panel.dataset.viewPanel!==view);if(view==='comparison')renderComparison();}

  $$('.gum-nav [data-view]').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.view)));
  $('#contextbar').addEventListener('click',event=>{const button=event.target.closest('[data-context]');if(!button||state.status==='Approved')return;syncPoint();state.calculationType=button.dataset.context;state.points.forEach(point=>{point.backendResult=null;});renderContext();});
  $('#jobId').addEventListener('change',()=>{const option=$('#jobId').selectedOptions[0];if(!option.value){state.jobId='';renderMeta();return;}if(option.dataset.status==='Completed'){state.jobId='';$('#jobId').value='';setMessage('Job Completed: this Job has already been completed and is locked. Request HOD authorization from the Job record.','validation-error');renderMeta();return;}state.jobId=option.value;state.jobNumber=option.dataset.number||'';state.jobStatus=option.dataset.status||'';state.customer=option.dataset.customer||'';state.projectNumber=option.dataset.projectNumber||'';state.projectName=option.dataset.projectName||'';state.mut=option.dataset.mut||'';state.mutAssetId=option.dataset.asset||'';state.serialNumber=option.dataset.serial||'';state.manufacturer=option.dataset.manufacturer||'';state.model=option.dataset.model||'';state.meterType=option.dataset.meter||'';state.rangeMin=option.dataset.rangeMin||'';state.rangeMax=option.dataset.rangeMax||'';state.rangeUnit=option.dataset.rangeUnit||'';state.flowPointCount=Math.max(1,Number(option.dataset.flowPointCount)||1);state.jobMethod=option.dataset.method||'';state.fluid=option.dataset.fluid||'';const configuredQuantity=String(option.dataset.quantity||'').toLowerCase();state.quantity=configuredQuantity.includes('volume')||volumeFlowUnits.has(state.rangeUnit)?'volume':'mass';state.analyst=option.dataset.analyst||state.analyst;state.calculationType=(state.jobMethod.toLowerCase().includes('coriolis')?'mutCor':'mutGrav');state.points=Array.from({length:state.flowPointCount},(_,index)=>({...blankPoint(),label:`Point ${index+1}`,flowUnit:state.rangeUnit}));state.activePoint=0;setMessage(`${state.flowPointCount} flow point${state.flowPointCount===1?'':'s'} loaded from the controlled Job record.`);renderAll();});
  $('#jobSearch').addEventListener('input',event=>{const term=event.target.value.toLowerCase();[...$('#jobId').options].forEach((option,index)=>{if(index)option.hidden=!option.textContent.toLowerCase().includes(term);});});
  ['#analyst','#calcDate','#fluid','#quantity'].forEach(id=>$(id).addEventListener('change',()=>{syncMeta();if(id==='#quantity')renderContext();}));
  ['#pointLabel','#nominalFlow','#flowUnit','#densityUnit','#refTemp','#refPressure','#coverageMode','#manualK','#coverageProb','#cmcExpression','#cmcA','#cmcB'].forEach(id=>$(id).addEventListener('change',()=>{syncPoint();currentPoint().backendResult=null;renderPoints();renderRuns();renderResult();}));
  $('#pointbar').addEventListener('click',event=>{const remove=event.target.closest('[data-delete-point]');if(remove){event.stopPropagation();state.points.splice(Number(remove.dataset.deletePoint),1);state.activePoint=Math.max(0,state.activePoint-1);renderContext();markDraftDirty();return;}const button=event.target.closest('[data-point]');if(button){syncPoint();state.activePoint=Number(button.dataset.point);renderContext();}});
  $('#addPointBtn').addEventListener('click',()=>{syncPoint();state.points.push(blankPoint());state.activePoint=state.points.length-1;renderContext();markDraftDirty();});
  $('#duplicatePointBtn').addEventListener('click',()=>{syncPoint();const duplicate=clone(currentPoint());duplicate.label=duplicate.label?`${duplicate.label} copy`:'';duplicate.backendResult=null;state.points.push(duplicate);state.activePoint=state.points.length-1;renderContext();markDraftDirty();});
  $('#addRunBtn').addEventListener('click',()=>{currentPoint().runs.push(state.calculationType.endsWith('Cor')?{masterEquipmentId:'',masterEquipmentLabel:'',master:'',correction:'',correctionBasis:'',mut:''}:{mass:'',time:'',density:'',mut:''});currentPoint().backendResult=null;renderRuns();renderResult();markDraftDirty();});
  const updateRun=event=>{const row=event.target.closest('[data-run]');if(row&&event.target.dataset.runKey){const run=currentPoint().runs[Number(row.dataset.run)];run[event.target.dataset.runKey]=event.target.value;currentPoint().backendResult=null;refreshObservationPreview();const evaluated=evaluateRun(run);row.querySelector('[data-reference-output]').textContent=format(evaluated?.reference_flow);row.querySelector('[data-error-output]').textContent=format(evaluated?.error_percent);renderTypeAStats();renderResult();}};
  $('#runTable').addEventListener('input',updateRun);
  $('#runTable').addEventListener('change',updateRun);
  $('#runTable').addEventListener('click',event=>{const remove=event.target.closest('[data-delete-run]');if(remove){currentPoint().runs.splice(Number(remove.dataset.deleteRun),1);currentPoint().backendResult=null;renderRuns();renderResult();markDraftDirty();}});
  $('#addSourceBtn').addEventListener('click',()=>{currentPoint().sources.push(blankSource());renderSources();markDraftDirty();});
  $('#loadTemplateBtn').addEventListener('click',()=>{const existing=new Set(currentPoint().sources.map(item=>item.name));(config.sourceTemplates[state.calculationType]||[]).forEach(name=>{if(!existing.has(name))currentPoint().sources.push(blankSource(name));});renderSources();markDraftDirty();});
  $('#sourceTable').addEventListener('input',event=>{const row=event.target.closest('[data-source]');if(row&&event.target.dataset.sourceKey){const source=currentPoint().sources[Number(row.dataset.source)];source[event.target.dataset.sourceKey]=event.target.type==='checkbox'?event.target.checked:event.target.value;currentPoint().backendResult=null;}});
  $('#sourceTable').addEventListener('change',event=>{const row=event.target.closest('[data-source]');if(row&&event.target.dataset.sourceKey){const source=currentPoint().sources[Number(row.dataset.source)];source[event.target.dataset.sourceKey]=event.target.type==='checkbox'?event.target.checked:event.target.value;currentPoint().backendResult=null;renderCorrelations();}});
  $('#sourceTable').addEventListener('click',event=>{const remove=event.target.closest('[data-delete-source]');if(remove){currentPoint().sources.splice(Number(remove.dataset.deleteSource),1);renderSources();renderCorrelations();markDraftDirty();return;}const select=event.target.closest('[data-equipment]');if(select){equipmentSourceIndex=Number(select.dataset.equipment);$('#equipmentModal').hidden=false;}});
  $('#addCorrelationBtn').addEventListener('click',()=>{currentPoint().correlations.push({source_i:'',source_j:'',coefficient:'',justification:''});renderCorrelations();markDraftDirty();});
  $('#correlationTable').addEventListener('input',event=>{const row=event.target.closest('[data-correlation]');if(row&&event.target.dataset.correlationKey){currentPoint().correlations[Number(row.dataset.correlation)][event.target.dataset.correlationKey]=event.target.value;currentPoint().backendResult=null;}});
  $('#correlationTable').addEventListener('click',event=>{const remove=event.target.closest('[data-delete-correlation]');if(remove){currentPoint().correlations.splice(Number(remove.dataset.deleteCorrelation),1);renderCorrelations();markDraftDirty();}});
  $('#closeEquipment').addEventListener('click',()=>{$('#equipmentModal').hidden=true;});
  $('#equipmentModal').addEventListener('click',event=>{if(event.target===event.currentTarget)event.currentTarget.hidden=true;const button=event.target.closest('[data-select-equipment]');if(button&&equipmentSourceIndex!==null){const equipment=JSON.parse(button.dataset.selectEquipment);const source=currentPoint().sources[equipmentSourceIndex];source.equipmentId=equipment.id;source.equipmentLabel=`${equipment.asset_number} · ${equipment.name}`;source.evidence=equipment.certificate_number||equipment.certificate_path||'';source.unit=source.unit||equipment.range_unit||'';source.value='';$('#equipmentModal').hidden=true;renderSources();}});
  $('#equipmentSearch').addEventListener('input',event=>{$$('[data-equipment-row]').forEach(row=>row.hidden=!row.dataset.search.toLowerCase().includes(event.target.value.toLowerCase()));});
  $('#calculatePointBtn').addEventListener('click',()=>calculate([currentPoint()],true).catch(()=>{})); $('#calculateBtn').addEventListener('click',()=>calculate().catch(()=>{})); $('#saveBtn').addEventListener('click',save);
  $('#newBtn').addEventListener('click',()=>{$('#newCalculationModal').hidden=false;});
  $('#cancelNewCalculation').addEventListener('click',()=>{$('#newCalculationModal').hidden=true;});
  $('#confirmNewCalculation').addEventListener('click',async()=>{await autosaveDraft();$('#newCalculationModal').hidden=true;state=initialState();state.standalone=$('#gumApp').dataset.standalone==='1';draftDirty=false;$('#jobSearch').value='';renderAll();setMessage(state.standalone?'New standalone calculation ready. Results will not be retained.':'New calculation ready. Select a Job.');});
  $('#workflowActions').addEventListener('click',event=>{const discard=event.target.closest('[data-discard-draft]');if(discard){discardDraft();return;}const button=event.target.closest('[data-workflow]');if(button)workflowAction(button.dataset.workflow);});
  $('#closeReviewAssignment').addEventListener('click',()=>{$('#reviewAssignmentModal').hidden=true;});
  $('#cancelReviewAssignment').addEventListener('click',()=>{$('#reviewAssignmentModal').hidden=true;});
  $('#confirmReviewAssignment').addEventListener('click',()=>{const reviewerUserId=value('#technicalReviewer'),approverUserId=value('#finalApprover');if(!reviewerUserId||!approverUserId){setMessage('Select both the Technical Reviewer and final Approving Officer.','validation-error');return;}if(reviewerUserId===approverUserId){setMessage('Technical Review and final approval must be assigned to different officers.','validation-error');return;}workflowAction('submit',{reviewerUserId,approverUserId});});
  $('#recordsTable').addEventListener('click',async event=>{const load=event.target.closest('[data-load-record]');if(load)loadRecord('calculation',load.dataset.loadRecord);const detail=event.target.closest('[data-record-detail]');if(detail){try{const body=await requestJson(`/uncertainty/api/records/calculation/${detail.dataset.recordId}/details/${detail.dataset.recordDetail}`);$('#recordDetailTitle').textContent=detail.textContent;$('#recordDetailBody').textContent=JSON.stringify(body.data,null,2);$('#recordDetailModal').hidden=false;}catch(error){setMessage(error.message,'validation-error');}}const revision=event.target.closest('[data-revision]');if(revision){const reason=window.prompt('Enter the reason for this revision:')||'';if(!reason)return;try{const body=await requestJson(`/uncertainty/api/records/calculation/${revision.dataset.revision}/revision`,{method:'POST',body:JSON.stringify({reason})});await loadRecord('calculation',body.record.id);}catch(error){setMessage(error.message,'validation-error');}}});
  $$('[data-load-cmc]').forEach(button=>button.addEventListener('click',()=>loadRecord('cmc',button.dataset.loadCmc)));
  $$('[data-cmc-revision]').forEach(button=>button.addEventListener('click',async()=>{const reason=window.prompt('Enter the reason for this CMC revision:')||'';if(!reason)return;try{const body=await requestJson(`/uncertainty/api/records/cmc/${button.dataset.cmcRevision}/revision`,{method:'POST',body:JSON.stringify({reason})});await loadRecord('cmc',body.record.id);}catch(error){setMessage(error.message,'validation-error');}}));
  $('#closeRecordDetail').addEventListener('click',()=>{$('#recordDetailModal').hidden=true;});
  function filterRecords(){const text=value('#recordSearch').toLowerCase(),status=value('#recordStatus');$$('[data-record-row]').forEach(row=>row.hidden=(!row.textContent.toLowerCase().includes(text)||(status&&row.dataset.status!==status)));}
  $('#recordSearch').addEventListener('input',filterRecords);$('#recordStatus').addEventListener('change',filterRecords);
  $('#gumApp').addEventListener('input',markDraftDirty);$('#gumApp').addEventListener('change',markDraftDirty);
  window.addEventListener('pagehide',()=>{if(!draftDirty||!canAutoSave())return;try{navigator.sendBeacon('/uncertainty/api/autosave',new Blob([JSON.stringify(payload())],{type:'application/json'}));}catch(error){}});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'){$('#infoPopover').hidden=true;$('#recordDetailModal').hidden=true;$('#newCalculationModal').hidden=true;}});
  if(state.standalone){
    $('#jobId').closest('label').hidden=true;
    ['#customer','#mut','#mutAssetId','#serialNumber','#manufacturer','#model','#meterType','#fluid'].forEach(id=>$(id).readOnly=false);
    $('#quantity').disabled=false;
    $('#jobMethod').closest('label').hidden=true;
    $('#jobRange').closest('label').hidden=true;
    $('#project').closest('label').hidden=true;
    $('#workflowActions').hidden=true;
  }
  renderAll();
  if(config.preselectedRecordId)loadRecord('calculation',config.preselectedRecordId);
  else if(config.preselectedJobId){$('#jobId').value=String(config.preselectedJobId);$('#jobId').dispatchEvent(new Event('change'));}
})();
