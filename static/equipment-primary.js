(()=>{
  const classification=document.getElementById('calibrationClassification');
  if(!classification)return;
  const fields=[...document.querySelectorAll('[data-primary-type-b]')];
  const sync=()=>{
    const primary=classification.value==='Primary Equipment';
    fields.forEach(element=>{
      element.hidden=!primary;
      for(const input of element.querySelectorAll('input'))input.required=primary&&input.name!=='degrees_of_freedom';
    });
  };
  classification.addEventListener('change',sync);sync();
})();
