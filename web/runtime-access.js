'use strict';
// Same-origin verified session and own exact organizational grants; no browser identity/tenant authority.
(() => {
  const element = id => document.getElementById(id);
  let contexts = [];
  let requestToken;
  let grantOptions = [];
  let pendingGrant;
  let grantBusy = false;
  function clearGrants() {
    grantOptions = [];
    pendingGrant = undefined;
    element('grant-options').replaceChildren();
    element('grant-admin').hidden = true;
    element('grant-confirm').checked = false;
    element('grant-apply').disabled = true;
    element('grant-scope').textContent = '';
  }
  function showGrant() {
    const grant = grantOptions[Number(element('grant-options').value)];
    const valid = grant && Date.parse(grant.validUntil) > Date.now();
    element('grant-scope').textContent = grant ? `Azione: ${grant.action}; Membership: ${grant.targetMembershipId}; Tenant: ${grant.tenantId}; Società: ${grant.legalEntityId}; Sede: ${grant.siteId}; Magazzino: ${grant.warehouseId}; Scadenza: ${grant.validUntil}; ${valid ? (grant.granted ? 'Concesso da questo mandato.' : 'Non concesso da questo mandato.') : 'Mandato scaduto: aggiorna.'}` : '';
    for (const id of ['grant-options','grant-operation','grant-confirm']) element(id).disabled=grantBusy;
    element('grant-apply').disabled = grantBusy || !valid || !requestToken || !element('grant-confirm').checked;
  }
  async function loadGrants() {
    const previous = grantOptions[Number(element('grant-options').value)];
    grantOptions = (await read('/api/v1/organization/grant-administration')).sort((a,b) => a.action.localeCompare(b.action) || a.targetMembershipId.localeCompare(b.targetMembershipId) || a.mandateId.localeCompare(b.mandateId));
    element('grant-options').replaceChildren(...grantOptions.map((grant,index) => {
      const option=document.createElement('option');
      option.value=String(index);
      option.textContent=`${grant.action} → ${grant.targetMembershipId} / ${grant.warehouseId}`;
      return option;
    }));
    const selected = previous && grantOptions.findIndex(grant => grant.mandateId === previous.mandateId && grant.targetMembershipId === previous.targetMembershipId);
    if (selected >= 0) element('grant-options').value=String(selected);
    element('grant-admin').hidden=grantOptions.length===0;
    element('grant-confirm').checked=false;
    showGrant();
  }
  function clearAssigned() {
    clearGrants();
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
      throw new Error(response.status === 401 ? 'Sessione terminata. Premi Riprova per accedere nuovamente.' : response.status === 403 ? 'Operazione non autorizzata nel contesto selezionato. Premi Riprova per aggiornare i permessi.' : response.status === 409 ? 'Conflitto: comando o permesso già utilizzato. Aggiorna con Riprova prima di una nuova conferma.' : 'Servizio non disponibile. Riprova.');
    }
    return response.json();
  }
  async function load() {
    requestToken = undefined;
    clearAssigned();
    element('grant-result').textContent='';
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
      await loadGrants();
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
  for (const id of ['grant-options','grant-operation']) element(id).addEventListener('change', () => {
    pendingGrant=undefined;
    element('grant-confirm').checked=false;
    element('grant-result').textContent='';
    showGrant();
  });
  element('grant-confirm').addEventListener('change',showGrant);
  element('grant-form').addEventListener('submit',async event => {
    event.preventDefault();
    const grant=grantOptions[Number(element('grant-options').value)];
    if (grantBusy || !requestToken || !element('grant-confirm').checked || !grant || Date.parse(grant.validUntil)<=Date.now()) return;
    grantBusy=true;
    showGrant();
    element('grant-result').textContent='Invio…';
    pendingGrant ??= {commandId:crypto.randomUUID(),mandateId:grant.mandateId,targetMembershipId:grant.targetMembershipId,
      tenantId:grant.tenantId,legalEntityId:grant.legalEntityId,siteId:grant.siteId,warehouseId:grant.warehouseId,
      action:grant.action,operation:element('grant-operation').value};
    try {
      requestToken=(await read('/auth/csrf')).requestToken;
      await read('/api/v1/organization/grant-commands',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-TOKEN':requestToken},body:JSON.stringify(pendingGrant)});
      const desired=pendingGrant.operation==='grant';
      pendingGrant=undefined;
      await loadGrants();
      const exact=grantOptions.find(row=>row.mandateId===grant.mandateId && row.targetMembershipId===grant.targetMembershipId);
      element('grant-result').textContent=exact && exact.granted===desired ? 'Permesso aggiornato e riletto.' : 'Stato cambiato nel frattempo: aggiorna i permessi con Riprova.';
    } catch(error) {
      element('grant-result').textContent=error.message;
      // No trust cached after an uncertain or rejected write; retry requires a fresh server projection.
      clearGrants();
    } finally { grantBusy=false; showGrant(); }
  });
  setInterval(showGrant,1000);
  void load();
})();
