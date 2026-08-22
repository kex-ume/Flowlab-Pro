(()=>{
  const table=document.getElementById('sourceTable');
  const modal=document.getElementById('equipmentModal');
  if(!table||!modal)return;
  let activeIndex=null;
  const selectedEquipment=new Map();
  const setField=(row,key,value)=>{
    const field=row.querySelector(`[data-source-key="${key}"]`);
    if(!field)return;
    if(key==='distribution'&&value==='normal'&&![...field.options].some(option=>option.value==='normal')){
      field.add(new Option('Normal','normal'));
    }
    field.value=value??'';
    field.dispatchEvent(new Event('input',{bubbles:true}));
    field.dispatchEvent(new Event('change',{bubbles:true}));
  };
  const applyProfile=(index,equipment,propertyName='calibration_uncertainty')=>{
    const row=table.querySelector(`[data-source="${index}"]`);
    const property=equipment?.source_properties?.[propertyName];
    if(!row||!property)return;
    setField(row,'name',property.name);
    setField(row,'sourceType','B');
    setField(row,'value',property.value);
    setField(row,'unit',property.unit);
    setField(row,'basis',property.basis);
    setField(row,'distribution',property.distribution);
    setField(row,'certK',property.certK);
    setField(row,'sensitivity',property.sensitivity);
    setField(row,'dof',property.dof);
    setField(row,'evidence',property.evidence);
    const cells=row.cells;
    if(cells[8])cells[8].textContent=property.divisor??'Server';
    if(cells[9])cells[9].textContent=property.standardUncertainty??'Server';
    if(cells[11])cells[11].textContent=property.contribution??'Server';
    const dof=row.querySelector('[data-source-key="dof"]');
    if(dof&&!property.dof)dof.placeholder='∞';
  };
  table.addEventListener('click',event=>{
    const button=event.target.closest('[data-equipment]');
    if(button)activeIndex=Number(button.dataset.equipment);
  });
  table.addEventListener('change',event=>{
    if(event.target.dataset.sourceKey!=='equipmentProperty')return;
    const row=event.target.closest('[data-source]');
    const index=Number(row?.dataset.source);
    applyProfile(index,selectedEquipment.get(index),event.target.value);
  });
  modal.addEventListener('click',event=>{
    const button=event.target.closest('[data-select-equipment]');
    if(!button||activeIndex===null)return;
    const equipment=JSON.parse(button.dataset.selectEquipment);
    selectedEquipment.set(activeIndex,equipment);
    const index=activeIndex;
    queueMicrotask(()=>applyProfile(index,equipment,'calibration_uncertainty'));
  });
})();
