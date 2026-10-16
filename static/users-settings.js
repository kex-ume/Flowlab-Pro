function closeUserPanel(panel) {
  panel.querySelectorAll('form').forEach(form => form.reset());
  panel.querySelectorAll('input[type=password]').forEach(input => { input.value = ''; });
  panel.open = false;
}
document.addEventListener('click', event => {
  const request=event.target.closest('.users-page [data-scroll-to]');
  if(request){
    document.querySelectorAll('.users-page .user-actions details[open]').forEach(closeUserPanel);
    document.querySelectorAll('.users-page [data-collapsible-form]').forEach(form=>{
      if(form.id!==request.dataset.scrollTo) form.hidden=true;
    });
  }
  const button = event.target.closest('[data-close-details]');
  if (!button) return;
  const panel = button.closest('details');
  if (!panel) return;
  closeUserPanel(panel);
  panel.querySelector('summary')?.focus();
});
// toggle does not bubble; capture closes other popovers before they can stack.
document.addEventListener('toggle', event => {
  const panel=event.target;
  if (!panel.matches('.users-page .user-actions details[open]')) return;
  document.querySelectorAll('.users-page [data-collapsible-form]').forEach(form=>{form.hidden=true;});
  document.querySelectorAll('.users-page .user-actions details[open]').forEach(other=>{
    if(other!==panel) closeUserPanel(other);
  });
},true);
document.querySelectorAll('.users-page .user-inline-form').forEach(form=>{
  const heading=document.createElement('div');heading.className='user-editor-heading';
  const title=document.createElement('strong');title.textContent=form.closest('details').querySelector('summary').textContent;
  const close=document.createElement('button');close.type='button';close.dataset.closeDetails='';close.className='user-editor-close';close.textContent='×';close.setAttribute('aria-label','Close '+title.textContent);
  heading.append(title,close);form.prepend(heading);
});
document.addEventListener('keydown', event => {
  if (event.key !== 'Escape') return;
  const panel = document.activeElement.closest('details[open]');
  panel?.querySelector('[data-close-details]')?.click();
});
