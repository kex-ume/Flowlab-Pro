(() => {
  const form = document.querySelector('#newJob form');
  if (!form) return;
  const uploadWrap = document.getElementById('serviceRequestUpload');
  const reason = document.getElementById('serviceRequestReason');
  const file = document.getElementById('serviceRequestFile');
  const status = document.getElementById('serviceRequestStatus');
  const field = name => form.elements.namedItem(name);
  const set = (name, value) => {
    const input = field(name);
    if (input && value !== null && value !== undefined && value !== '') input.value = value;
  };
  const syncChoice = () => {
    const choice = field('service_request_required')?.value;
    uploadWrap.hidden = choice !== 'yes';
    reason.hidden = choice !== 'no';
    file.required = choice === 'yes';
    field('service_request_exception_reason').required = choice === 'no';
  };
  form.querySelectorAll('[name="service_request_required"]').forEach(item => item.addEventListener('change', syncChoice));
  file.addEventListener('change', async () => {
    if (!file.files.length) return;
    status.textContent = 'Reading Service Request...';
    const body = new FormData(); body.append('service_request', file.files[0]);
    try {
      const response = await fetch('/api/service-request/preview', {method: 'POST', body});
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error(payload.error || 'Unable to read the Service Request.');
      const data = payload.data;
      set('mut_description', data.service_description || (data.meter_type ? `${data.meter_type} flow meter` : ''));
      set('mut_serial_number', data.serial_number); set('manufacturer', data.manufacturer);
      set('model_number', data.model_number); set('meter_type', data.meter_type);
      set('meter_size', data.meter_size); set('flow_point_count', data.flow_point_count);
      set('flow_min', data.flow_min); set('flow_max', data.flow_max); set('flow_unit', data.flow_unit);
      set('specification_reference', data.specification_reference);
      set('lower_tolerance', data.lower_tolerance); set('upper_tolerance', data.upper_tolerance);
      set('tolerance_unit', data.tolerance_unit || '%');
      if (data.conformity_required) set('conformity_required', 'yes');
      if ((data.decision_rule_code || '').toUpperCase().includes('DR-02')) set('decision_rule_code', 'DR-02');
      status.textContent = 'Service Request read. Confirm the populated Job and conformity fields before creating the Job.';
      status.classList.add('success');
    } catch (error) {
      status.textContent = error.message; status.classList.remove('success');
    }
  });
  syncChoice();
})();
