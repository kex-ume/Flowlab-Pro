(()=>{
  const table=document.getElementById('runTable');
  const quantity=document.getElementById('quantity');
  const densityUnit=document.getElementById('densityUnit');
  if(!table)return;
  const unlockDensity=()=>table.querySelectorAll('[data-run-key="density"]').forEach(input=>{
    const volumetric=quantity?.value==='volume';
    input.disabled=!volumetric;
    input.placeholder=volumetric?`Required · ${densityUnit?.value||'kg/m³'}`:'Not applicable to mass flow';
    input.title=volumetric?'Enter the value using the selected density input basis. FlowLab Pro converts the reference into the point flow unit.':'Density is excluded from the mass-flow model.';
  });
  new MutationObserver(unlockDensity).observe(table,{childList:true,subtree:true});
  quantity?.addEventListener('change',unlockDensity);
  densityUnit?.addEventListener('change',unlockDensity);
  unlockDensity();
})();
