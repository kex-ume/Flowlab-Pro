(() => {
  const lab = document.getElementById('registrationLab');
  if (!lab) return;
  const update = () => {
    for (const kind of ['flow','ei']) {
      document.querySelectorAll(`[data-registration-${kind}]`).forEach(label => {
        const enabled = lab.value === kind;
        label.hidden = !enabled;
        label.style.display = enabled ? '' : 'none';
        label.querySelectorAll('input,textarea,select').forEach(input => input.disabled = !enabled);
      });
    }
  };
  lab.addEventListener('change', update);
  update();
})();
