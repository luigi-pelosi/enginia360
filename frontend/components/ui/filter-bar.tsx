"use client";

import {useEffect,useRef,useState,type ReactNode} from 'react';
import {useTranslations} from 'next-intl';
import {SlidersHorizontal} from 'lucide-react';

export type FilterBarField={key:string;content:ReactNode;minWidth?:number;grow?:boolean};
export type FilterBarProps={id:string;fields:FilterBarField[];expanded?:boolean;onExpandedChange?:(expanded:boolean)=>void};
const gap=12,toggleSpace=36+gap;
/** Mantiene disponibile il primo filtro anche nei contenitori più stretti. */
export function filterBarVisibleCount(fields:FilterBarField[],width:number):number{
 if(!fields.length)return 0;
 const minimum=(field:FilterBarField)=>field.minWidth??144;
 const total=fields.reduce((sum,field)=>sum+minimum(field),0)+gap*(fields.length-1);
 if(total<=width)return fields.length;
 let count=1,used=minimum(fields[0]);
 while(count<fields.length&&used+gap+minimum(fields[count])+toggleSpace<=width){used+=gap+minimum(fields[count]);count++;}
 return count;
}
export function FilterBar({id,fields,expanded,onExpandedChange}:FilterBarProps){
 const t=useTranslations('app'),container=useRef<HTMLDivElement>(null);
 const [width,setWidth]=useState(0),[internalExpanded,setInternalExpanded]=useState(false);
 const open=expanded??internalExpanded,visible=filterBarVisibleCount(fields,width),overflow=visible<fields.length;
 useEffect(()=>{
  const element=container.current;if(!element)return;
  setWidth(element.getBoundingClientRect().width);
  if(typeof ResizeObserver==='undefined')return;
  const observer=new ResizeObserver(entries=>{if(entries[0])setWidth(entries[0].contentRect.width);});
  observer.observe(element);return()=>observer.disconnect();
 },[]);
 function toggle(){if(expanded===undefined)setInternalExpanded(!open);onExpandedChange?.(!open);}
 function field(entry:FilterBarField,index:number,primary:boolean){return <div key={entry.key} data-filter-key={entry.key} className="min-w-0" style={{flex:`${entry.grow?1:0} ${primary&&index===0?1:0} ${entry.minWidth??144}px`,minWidth:primary&&index===0?0:entry.minWidth??144}}>{entry.content}</div>;}
 return <div id={id} data-slot="filter-bar" ref={container} className="min-w-0 p-4">
  <div data-filter-primary className="flex flex-nowrap items-end gap-3 min-w-0">
   {fields.slice(0,visible).map((entry,index)=>field(entry,index,true))}
   {overflow&&<button id={`${id}-toggle`} type="button" className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md border hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label={t('moreFilters')} title={t('moreFilters')} aria-expanded={open} aria-controls={`${id}-more`} onClick={toggle}><SlidersHorizontal size={16} aria-hidden="true"/></button>}
  </div>
  <div id={`${id}-more`} role="region" aria-label={t('moreFilters')} hidden={!overflow||!open}>
   <div className="flex flex-wrap items-end gap-3 pt-3">{fields.slice(visible).map((entry,index)=>field(entry,index,false))}</div>
  </div>
 </div>;
}
