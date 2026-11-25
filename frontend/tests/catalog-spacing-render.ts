import {renderToStaticMarkup} from 'react-dom/server';
import React from 'react';
import {readdirSync} from 'node:fs';
import {readFileSync} from 'node:fs';
import {catalogHarness, catalogSession} from './catalog-harness.ts';
import {itemHarness} from './catalog-items-harness.ts';

// Render the real workspace trees using the existing isolated API/UI harnesses.
// UI primitives become simple DOM nodes; spacing classes and heading controls are retained.
function dom(node:any):any {
 if (node == null || typeof node === 'boolean') return null;
 if (Array.isArray(node)) return node.map(dom);
 if (typeof node !== 'object') return node;
 if (!node.props) return null;
 const name = typeof node.type === 'string' ? node.type : node.type?.name;
 if (name === 'Dialog') return null;
 const tag = name === 'Button' ? 'button' : typeof node.type === 'string' ? node.type : 'div';
 const {children,className,id,disabled,...rest}=node.props;
 const attrs:any={className,id,disabled};
 if (rest['data-catalog-workspace']) attrs['data-catalog-workspace']=rest['data-catalog-workspace'];
 return React.createElement(tag,attrs,dom(children));
}
const pages:any={};
for (const resource of ['catalog-numbering','catalog-types','catalog-categories','catalog-units','catalog-brands']) {
 const session={...catalogSession,permissions:[...catalogSession.permissions,'catalog-brands.read','catalog-brands.create']};
 const h=catalogHarness(resource,(path)=>path==='/session'?session:({items:[],total:0}),undefined,'it',session); await h.settle();
 pages[resource]=renderToStaticMarkup(dom(h.tree)); h.unmount();
}
const h=itemHarness(); await h.settle(); pages['catalog-items']=renderToStaticMarkup(dom(h.tree)); h.unmount();
const css=readdirSync('.next/static/css').filter(x=>x.endsWith('.css')).map(x=>readFileSync('.next/static/css/'+x,'utf8')).join('\n');
console.log(JSON.stringify({pages,css}));
