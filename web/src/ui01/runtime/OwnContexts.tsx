import { useEffect, useState } from 'react';
import { request } from './workshopApi';
import { check, record, uuid } from './contracts';
type OwnContext = Readonly<{ tenantId: string; tenantName: string; legalEntityId: string; legalEntityName: string; siteId: string; siteName: string; warehouseId: string; warehouseName: string; capabilityEnabled: boolean | null; canWrite: boolean }>;
export default function OwnContexts({ onError }: Readonly<{ onError: (error: unknown) => void }>) {
  const [rows, setRows] = useState<readonly OwnContext[]>([]), [selected, setSelected] = useState('0'), [message, setMessage] = useState('Lettura propri contesti…');
  useEffect(() => { let active = true; void request('/api/v1/organization/contexts').then(value => {
    check(Array.isArray(value)); const contexts = value.map(v => { const r = record(v); check(['tenantId','legalEntityId','siteId','warehouseId'].every(k => uuid(r[k])) && ['tenantName','legalEntityName','siteName','warehouseName'].every(k => typeof r[k] === 'string') && r.readPermission === 'organization-context.read' && r.capability === 'organization-context' && (r.capabilityEnabled === null || typeof r.capabilityEnabled === 'boolean') && typeof r.canWrite === 'boolean'); return r as OwnContext; });
    if (active) { setRows(contexts); setMessage(contexts.length ? 'Propri scope verificati' : 'Nessun contesto organizzativo assegnato.'); }
  }).catch(e => { if (active) { setMessage((e as Error).message); onError(e); } }); return () => { active = false; }; }, []);
  const row = rows[Number(selected)];
  return <details><summary>Contesto organizzativo</summary><p>{message}</p><label>Proprio scope<select value={selected} onChange={e => setSelected(e.target.value)}>{rows.map((r,i) => <option key={i} value={i}>{r.tenantName} / {r.legalEntityName} / {r.siteName} / {r.warehouseName}</option>)}</select></label>{row && <p>organization-context: {row.capabilityEnabled === null ? 'Non configurata' : row.capabilityEnabled ? 'Attiva' : 'Disabilitata'} · canWrite: {String(row.canWrite)}</p>}<p>canWrite riguarda solo organization-context.write, non autorizza né limita Workshop.</p></details>;
}
