'use strict';
// Same-origin verified session and own exact organizational grants; no browser identity/tenant authority.
(() => {
  const element = id => document.getElementById(id);
  let contexts = [];
  let requestToken;
  function clearAssigned() {
    contexts = [];
    element('contexts').replaceChildren();
    element('scope').textContent = element('capability').textContent = element('result').textContent = '';
    element('assigned').hidden = true;
    element('write').disabled = true;
  }
  function showSelection() {
    const context = contexts[Number(element('contexts').value)];
    element('scope').textContent = context ? `Azione: ${context.readPermission}; Società: ${context.legalEntityName}; Sede: ${context.siteName}; Magazzino: ${context.warehouseName}.` : '';
    const state = context?.capabilityEnabled;
    element('capability').textContent = context ? `${context.capability}: ${state === true ? 'Attiva' : state === false ? 'Disabilitata — consultazione storica autorizzata.' : 'Non configurata — nessuna nuova operazione.'}` : '';
    element('write').disabled = !requestToken || context?.canWrite !== true;
  }
  async function read(path, options) {
    const response = await fetch(path, {cache:'no-store', ...options});
    if (!response.ok) {
      if (response.status === 401) { requestToken = undefined; clearAssigned(); }
      throw new Error(response.status === 401 ? 'Sessione terminata. Premi Riprova per accedere nuovamente.' : response.status === 403 ? 'Operazione non autorizzata nel contesto selezionato. Premi Riprova per aggiornare i permessi.' : 'Servizio non disponibile. Riprova.');
    }
    return response.json();
  }
  async function load() {
    requestToken = undefined;
    clearAssigned();
    element('login').hidden = element('logout').hidden = true;
    element('retry').disabled = true;
    element('status').textContent = 'Verifica sessione…';
    try {
      const session = await read('/auth/session');
      requestToken = (await read('/auth/csrf')).requestToken;
      const form = element(session.authenticated ? 'logout' : 'login');
      form.querySelector('input').value = requestToken;
      form.hidden = false;
      if (!session.authenticated) {
        element('status').textContent = 'Accesso richiesto.';
        return;
      }
      contexts = await read('/api/v1/organization/contexts');
      element('contexts').replaceChildren(...contexts.map((context, index) => {
        const option = document.createElement('option');
        option.value = String(index);
        option.textContent = `${context.tenantName} / ${context.legalEntityName} / ${context.siteName} / ${context.warehouseName}`;
        return option;
      }));
      element('status').textContent = contexts.length ? 'Sessione attiva.' : 'Sessione attiva, nessun contesto assegnato.';
      element('assigned').hidden = contexts.length === 0;
      showSelection();
    } catch (error) {
      requestToken = undefined;
      clearAssigned();
      element('status').textContent = error.message;
    } finally { element('retry').disabled = false; }
  }
  element('contexts').addEventListener('change', showSelection);
  element('retry').addEventListener('click', load);
  element('note').addEventListener('submit', async event => {
    event.preventDefault();
    const context = contexts[Number(element('contexts').value)];
    if (!context || context.canWrite !== true || !requestToken) return;
    element('write').disabled = true;
    element('result').textContent = 'Invio…';
    try {
      requestToken = (await read('/auth/csrf')).requestToken;
      const created = await read('/api/v1/organization/context-notes', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRF-TOKEN':requestToken},
        body:JSON.stringify({tenantId:context.tenantId,legalEntityId:context.legalEntityId,siteId:context.siteId,warehouseId:context.warehouseId,message:element('message').value}),
      });
      const persisted = await read('/api/v1/organization/context-notes/'+encodeURIComponent(created.id));
      element('result').textContent = 'Nota riletta: ' + persisted.message;
    } catch (error) { element('result').textContent = error.message; }
    finally { showSelection(); }
  });
  void load();
})();
