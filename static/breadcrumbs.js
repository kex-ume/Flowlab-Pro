/* Reflect inline Add forms without changing their submit/save behaviour. */
(() => {
  const nav=document.querySelector('.app-breadcrumbs');
  if(!nav)return;
  const list=nav.querySelector('ol');
  let observer;
  function restore(){
    list.querySelector('[data-form-crumb]')?.remove();
    list.lastElementChild?.querySelector('a')?.setAttribute('aria-current','page');
    observer?.disconnect();
  }
  document.addEventListener('click',event=>{
    const trigger=event.target.closest('[data-scroll-to],[data-ei-toggle],[data-breadcrumb-target],button[aria-controls]');
    if(!trigger)return;
    const panel=document.getElementById(trigger.dataset.scrollTo || trigger.dataset.eiToggle || trigger.dataset.breadcrumbTarget || trigger.getAttribute('aria-controls'));
    if(!panel || !(panel.matches('[data-collapsible-form]') || panel.querySelector('form')))return;
    requestAnimationFrame(()=>{
      restore();
      if(panel.hidden)return;
      list.querySelector('[aria-current]')?.removeAttribute('aria-current');
      const item=document.createElement('li');item.dataset.formCrumb='';
      const chevron=document.createElementNS('http://www.w3.org/2000/svg','svg');chevron.setAttribute('viewBox','0 0 16 16');chevron.setAttribute('aria-hidden','true');
      const path=document.createElementNS(chevron.namespaceURI,'path');path.setAttribute('d','m6 3 5 5-5 5');chevron.append(path);
      const link=document.createElement('a');link.textContent=trigger.textContent.trim().replace(/^\+\s*/,'');link.href=location.pathname+location.search+'#'+encodeURIComponent(panel.id);link.setAttribute('aria-current','page');
      link.addEventListener('click',e=>{e.preventDefault();panel.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});});
      item.append(chevron,link);list.append(item);
      observer=new MutationObserver(()=>{if(panel.hidden)restore();});observer.observe(panel,{attributes:true,attributeFilter:['hidden']});
    });
  });
})();
