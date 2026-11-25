import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {readdirSync,readFileSync} from 'node:fs';
import {catalogHarness,catalogSession,findCatalog} from './catalog-harness.ts';
function dom(node:any):any {
 if(node==null||typeof node==='boolean')return null;
 if(Array.isArray(node))return node.map(dom);
 if(typeof node!=='object')return node;
 if(!node.props)return null;
 const name=typeof node.type==='string'?node.type:node.type?.name;
 const tag=typeof node.type==='string'?node.type:({Input:'input',Textarea:'textarea',Label:'label',Switch:'button'} as any)[name]||'div';
 const {children,className,id,disabled,htmlFor}=node.props;
 return React.createElement(tag,{className,id,disabled,htmlFor},dom(children));
}
const pages:any={};
for(const resource of ['catalog-brands','catalog-categories','catalog-types','catalog-units'])for(const readonly of [false,true]){
 const row={id:'r',name:'Test',code:'T',is_active:true,kind:'GOOD',version:1,conversion_scope:'UNIVERSAL',dimension:'LENGTH',decimal_places:2};
 const session={...catalogSession,permissions:[...catalogSession.permissions,...['read','create','update'].map(a=>resource+'.'+a)]};
 const h=catalogHarness(resource,p=>p==='/session'?session:p.includes('/r?')?row:{items:[row],total:1},undefined,'it',session);
 await h.settle(); if(readonly)await h.action('Dettagli Test').props.onClick();else await h.byId('catalog-new').props.onClick(); await h.settle();
 const grid=findCatalog(h.tree,n=>n.props?.className==='grid gap-4 sm:grid-cols-2');
 pages[resource+':'+readonly]=renderToStaticMarkup(dom(grid));h.unmount();
}
const css=readdirSync('.next/static/css').filter(x=>x.endsWith('.css')).map(x=>readFileSync('.next/static/css/'+x,'utf8')).join('\n');
console.log(JSON.stringify({pages,css}));
