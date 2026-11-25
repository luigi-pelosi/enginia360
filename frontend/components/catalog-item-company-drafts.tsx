"use client";
import {useState} from 'react';
import {useTranslations} from 'next-intl';
import {Plus,Pencil,Trash2} from 'lucide-react';
import type {Row} from '@/lib/model';
import type {CatalogCompanyOption} from '@/lib/catalog-companies';
import {itemCompanyInitial,itemCompanyUnits,type ItemCompanyDraft,type ItemKind,type ItemRecord} from '@/lib/catalog-items';
import {Button} from '@/components/ui/button';
import {Label} from '@/components/ui/label';
import {Switch} from '@/components/ui/switch';
import {Badge} from '@/components/ui/badge';
import {Select,SelectContent,SelectItem,SelectTrigger,SelectValue} from '@/components/ui/select';
import {Dialog,DialogContent,DialogHeader,DialogTitle,DialogDescription,DialogFooter} from '@/components/ui/dialog';
import {Table,TableHeader,TableBody,TableRow,TableHead,TableCell} from '@/components/ui/table';
export type CatalogItemCompanyDraftsProps={companyDrafts:ItemCompanyDraft[];companyOptions:CatalogCompanyOption[];types:Row[];units:Row[];record:ItemRecord;selectedTypeId:unknown;kind:ItemKind;baseId:unknown;disabled:boolean;loading:boolean;onChange:(rows:ItemCompanyDraft[])=>void};
// La bozza persistita appartiene all'ItemEditor padre; questa finestra non invia comandi HTTP.
export function CatalogItemCompanyDrafts({companyDrafts,companyOptions,types,units,record,selectedTypeId,kind,baseId,disabled,loading,onChange}:CatalogItemCompanyDraftsProps){
 const t=useTranslations('catalogCompanies'),a=useTranslations('app'),c=useTranslations('catalog');
 const [editor,setEditor]=useState<{originalId:string|null;draft:ItemCompanyDraft}|null>(null),[error,setError]=useState('');
 const eligible=companyOptions.filter(company=>company.is_enabled&&company.permissions.includes('read')&&company.permissions.includes('create'));
 const available=eligible.filter(company=>!companyDrafts.some(row=>row.company_id===company.id&&row.company_id!==editor?.originalId));
 const associated=itemCompanyUnits(baseId,record.units,units),blocked=disabled||loading;
 const unitLabel=(id:unknown)=>String(units.find(unit=>unit.id===id)?.name??id??t('baseUom'));
 function open(row?:ItemCompanyDraft){
  if(blocked)return;
  const company=eligible.find(company=>!companyDrafts.some(draft=>draft.company_id===company.id));
  if(!row&&!company)return;
  setError('');setEditor({originalId:row?.company_id??null,draft:row?structuredClone(row):{company_id:company!.id,values:itemCompanyInitial(types.find(type=>type.id===selectedTypeId),kind)}});
 }
 function save(event:{preventDefault:()=>void;stopPropagation:()=>void}){
  event.preventDefault();event.stopPropagation();if(!editor||blocked)return;
  if(!available.some(company=>company.id===editor.draft.company_id)){setError(t('draftCompanyUnavailable'));return;}
  if(kind!=='GOOD'&&editor.draft.values.track_stock){setError(t('draftStockInvalid'));return;}
  if([editor.draft.values.default_sales_uom_id,editor.draft.values.default_purchase_uom_id].some(id=>id&&!associated.some(unit=>unit.id===id))){setError(t('draftUnitInvalid'));return;}
  const next=editor.originalId?companyDrafts.map(row=>row.company_id===editor.originalId?editor.draft:row):[...companyDrafts,editor.draft];
  onChange(next);setEditor(null);setError('');
 }
 return <div data-testid="catalog-item-company-drafts" className="space-y-3 min-w-0">
  <div className="flex items-center justify-between gap-3"><p className="text-sm text-muted-foreground">{t('draftDescription')}</p><Button id="catalog-company-draft-add" type="button" variant="outline" size="sm" disabled={blocked||!eligible.some(company=>!companyDrafts.some(row=>row.company_id===company.id))} onClick={()=>open()}><Plus size={16}/>{t('associate')}</Button></div>
  <Table id="catalog-company-drafts-table" className="w-full text-sm"><TableHeader><TableRow><TableHead>{t('company')}</TableHead><TableHead kind="status">{t('enabled')}</TableHead><TableHead kind="status">{t('configuration')}</TableHead><TableHead>{t('default_sales_uom_id')}</TableHead><TableHead>{t('default_purchase_uom_id')}</TableHead><TableHead kind="actions" className="w-20 min-w-20 max-w-20">{a('actions')}</TableHead></TableRow></TableHeader><TableBody>
   {!companyDrafts.length&&<TableRow><TableCell colSpan={6}>{a(loading?'loading':'empty')}</TableCell></TableRow>}
   {companyDrafts.map(row=><TableRow key={row.company_id} data-company-id={row.company_id}><TableCell>{companyOptions.find(company=>company.id===row.company_id)?.name??row.company_id}</TableCell><TableCell kind="status"><Badge variant={row.values.is_enabled?'default':'secondary'}>{t(row.values.is_enabled?'ENABLED':'DISABLED')}</Badge></TableCell><TableCell kind="status"><div className="flex flex-wrap justify-center gap-1">{(['is_sellable','is_purchasable','track_stock'] as const).map(name=><Badge key={name} variant="secondary">{t(name)}: {c(row.values[name]?'yes':'no')}</Badge>)}</div></TableCell><TableCell>{row.values.default_sales_uom_id?unitLabel(row.values.default_sales_uom_id):t('baseUom')}</TableCell><TableCell>{row.values.default_purchase_uom_id?unitLabel(row.values.default_purchase_uom_id):t('baseUom')}</TableCell><TableCell kind="actions" className="w-20 min-w-20 max-w-20 whitespace-nowrap"><Button id={'catalog-company-draft-edit-'+row.company_id} type="button" variant="ghost" size="icon" className="size-8" disabled={blocked} aria-label={a('edit')+' '+(companyOptions.find(company=>company.id===row.company_id)?.name??row.company_id)} onClick={()=>open(row)}><Pencil size={16}/></Button><Button id={'catalog-company-draft-remove-'+row.company_id} type="button" variant="ghost" size="icon" className="size-8" disabled={disabled} aria-label={a('delete')+' '+(companyOptions.find(company=>company.id===row.company_id)?.name??row.company_id)} onClick={()=>onChange(companyDrafts.filter(draft=>draft.company_id!==row.company_id))}><Trash2 size={16}/></Button></TableCell></TableRow>)}
  </TableBody></Table>
  {editor&&<Dialog open onOpenChange={open=>{if(!open&&!disabled){setEditor(null);setError('');}}}><DialogContent data-testid="catalog-company-draft-editor" className="sm:max-w-xl max-h-[85dvh] overflow-auto"><DialogHeader><DialogTitle>{t(editor.originalId?'configuration':'associate')}</DialogTitle><DialogDescription>{t('draftDescription')}</DialogDescription></DialogHeader>
   <form data-catalog-company-draft-form className="space-y-4" onSubmit={save}>{error&&<p role="alert" className="text-destructive">{error}</p>}
    <div className="space-y-2"><Label htmlFor="catalog-company-draft-company" required>{t('company')}</Label><Select value={editor.draft.company_id} disabled={blocked} required onValueChange={company_id=>{if(available.some(company=>company.id===company_id))setEditor({...editor,draft:{...editor.draft,company_id}});}}><SelectTrigger id="catalog-company-draft-company" className="w-full"><SelectValue/></SelectTrigger><SelectContent>{!available.some(company=>company.id===editor.draft.company_id)&&<SelectItem value={editor.draft.company_id} disabled>{companyOptions.find(company=>company.id===editor.draft.company_id)?.name??editor.draft.company_id}</SelectItem>}{available.map(company=><SelectItem key={company.id} value={company.id}>{company.name}</SelectItem>)}</SelectContent></Select></div>
    {(['is_enabled','is_sellable','is_purchasable','track_stock'] as const).map(name=><div key={name} className="flex items-center justify-between gap-3"><Label htmlFor={'catalog-company-draft-'+name.replaceAll('_','-')}>{t(name)}</Label><Switch id={'catalog-company-draft-'+name.replaceAll('_','-')} checked={editor.draft.values[name]} disabled={blocked||name==='track_stock'&&kind!=='GOOD'&&!editor.draft.values.track_stock} onCheckedChange={value=>setEditor({...editor,draft:{...editor.draft,values:{...editor.draft.values,[name]:value}}})}/></div>)}
    {kind!=='GOOD'&&<p className="text-sm text-muted-foreground">{t('stockGoodsOnly')}</p>}
    {(['default_sales_uom_id','default_purchase_uom_id'] as const).map(name=>{const value=editor.draft.values[name]??'BASE';return <div className="space-y-2" key={name}><Label htmlFor={'catalog-company-draft-'+name.replaceAll('_','-')}>{t(name)}</Label><Select value={value} disabled={blocked} onValueChange={value=>setEditor({...editor,draft:{...editor.draft,values:{...editor.draft.values,[name]:value==='BASE'?null:value}}})}><SelectTrigger id={'catalog-company-draft-'+name.replaceAll('_','-')} className="w-full"><SelectValue/></SelectTrigger><SelectContent><SelectItem value="BASE">{t('baseUom')} · {unitLabel(baseId)}</SelectItem>{value!=='BASE'&&!associated.some(unit=>unit.id===value)&&<SelectItem value={value} disabled>{t('unavailableUnit')} · {unitLabel(value)}</SelectItem>}{associated.map(unit=><SelectItem key={unit.id} value={unit.id}>{String(unit.name)}{unit.code?' · '+unit.code:''}</SelectItem>)}</SelectContent></Select></div>;})}
    <DialogFooter><Button id="catalog-company-draft-cancel" type="button" variant="outline" disabled={disabled} onClick={()=>{setEditor(null);setError('');}}>{a('cancel')}</Button><Button id="catalog-company-draft-save" type="submit" disabled={blocked}>{a('save')}</Button></DialogFooter>
   </form>
  </DialogContent></Dialog>}
 </div>;
}
