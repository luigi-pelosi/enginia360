#!/usr/bin/env python3
"""Offline decoder of minimized owned captures, not a provider adapter/schema.

Accepts only the two acquired projection shapes. No network, configuration,
coercion, retries, acknowledgement mapping or draft/fiscal-finality inference.
"""
import json
import math

def decode(text):
    value=json.loads(text)
    if not isinstance(value,dict) or value.get('responseCode')!=200 or value.get('errorCode')!=0:
        raise ValueError('successful captured business envelope required')
    if 'document' in value and 'stockReports' not in value:
        doc=value['document']
        if not isinstance(doc,dict) or type(doc.get('id')) is not int or not isinstance(doc.get('docStatus'),str):
            raise ValueError('captured document identity/status required')
        rows=doc.get('rows')
        if not isinstance(rows,list):raise ValueError('captured rows required')
        ids=set()
        for row in rows:
            if not isinstance(row,dict) or type(row.get('idPos')) is not int or row['idPos'] in ids:
                raise ValueError('distinct integer row identity required; SKU is not identity')
            ids.add(row['idPos'])
            quantity=row.get('quantity')
            if isinstance(quantity,bool) or not isinstance(quantity,(int,float)) or not math.isfinite(quantity):
                raise ValueError('finite captured numeric quantity required; no coercion')
            if row.get('idMaterial') is not None and not isinstance(row['idMaterial'],str):
                raise ValueError('captured material string or null required')
    elif 'stockReports' in value and 'document' not in value:
        if not isinstance(value['stockReports'],list):raise ValueError('captured stock rows required')
        for row in value['stockReports']:
            if not isinstance(row,dict):raise ValueError('captured stock object required')
            for field in ('quantity','reservedByOrdersQty','availableQty','orderedToSuppliersQty','stockForecastQty'):
                number=row.get(field)
                if isinstance(number,bool) or not isinstance(number,(int,float)) or not math.isfinite(number):
                    raise ValueError('finite captured stock number required; no coercion')
    else:
        raise ValueError('unsupported captured shape')
    return value
