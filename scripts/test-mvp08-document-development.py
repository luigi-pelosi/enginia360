#!/usr/bin/env python3
"""MVP08 SQL acceptance sources. UNEXECUTED until whole #147 source complete."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import uuid
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('documents07',ROOT/'scripts/test-mvp07-documents-inventory.py')
prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
uid=prior.uid;lit=prior.lit
@unittest.skipUnless(os.environ.get('R00_MIGRATION_TESTS')=='1','isolated PostgreSQL required')
class DocumentDevelopmentTests(unittest.TestCase):
 locals().update({k:v for k,v in vars(prior.DocumentInventoryTests).items() if callable(v) and not k.startswith('test')})
 def migrate(self,manifest=None):
  result=prior.DocumentInventoryTests.migrate(self,manifest)
  if result[0]:
   print('MVP08_MIGRATION_NONPASS\n'+result[1]+'\n'+result[2],flush=True)
  return result
 def prepare_development(self):
  self.prepare_documents();self.role_revision=1
  for action,site in [('documents.develop',self.site),('document-types.paths.manage',None)]:
   request=self.role_payload('permission',label=action,action=action,legalEntityId=self.company,siteId=site,warehouseId=None)
   reply=self.role_command(request);self.assertEqual(reply['state'],'applied');self.permissions.append((request,reply['snapshot']))
  self.update_role()
 def update_role(self,permissions=None):
  self.role_snapshot=self.role_command(dict(self.role_request,commandId=uid(),resourceId=self.role_snapshot['resourceId'],expectedRevision=self.role_revision,permissionIds=permissions or [s['resourceId'] for _,s in self.permissions]))['snapshot'];self.role_revision+=1
 def path(self,source='Load',destination='None',enabled=True,cross=False,revision=0):
  request=dict(commandId=uid(),operation='path',legalEntityId=self.company,sourceTypeId=self.types[source]['id'],destinationTypeId=self.types[destination]['id'],expectedRevision=revision,enabled=enabled,allowCrossSite=cross)
  return self.app_result('SELECT document_types.command('+lit(json.dumps(request))+'::jsonb)')
 def origin(self,source,quantity='1',index=0,revision=1):
  return dict(sourceDocumentId=source['id'],sourceLineId=source['lines'][index]['id'],quantity=quantity,expectedPathRevision=revision)
 def developed(self,sources,quantities=None,effect='None',merged=False,**changes):
  quantities=quantities or ['1']*len(sources)
  lines=[]
  for source,q in zip(sources,quantities):
   line=source['lines'][0]
   lines.append(self.line(q,item=line['itemId'],catalogRevision=line['catalogRevision'],warehouse=self.warehouse if effect!='None' and line['kind']=='Article' else None,destination=self.destination if effect=='Transfer' and line['kind']=='Article' else None,origins=[self.origin(source,q)]))
  if merged:
   first=lines[0];first['origins']=[o for l in lines for o in l['origins']];first['quantity']=str(sum(Decimal(q) for q in quantities));lines=[first]
  result=self.draft(effect,lines=lines,operation='develop');result.update(changes);return result
 def confirmed_none(self,quantity='3',item=None):
  draft=self.doc(self.draft('None',lines=[self.line(quantity,item=item)]))['snapshot'];return self.doc(self.confirm(draft))['snapshot']
 def stage(self,source,destination='None'):
  return next(s for s in self.read(source['id'])['stages'] if s['lineId']==source['lines'][0]['id'] and s['destinationTypeId']==self.types[destination]['id'])
 def owned_facts(self):
  return self.counts()|json.loads(self.sql("SELECT jsonb_build_object('origins',(SELECT coalesce(jsonb_agg(to_jsonb(o) ORDER BY to_jsonb(o)::text),'[]') FROM documents.origins o),'passages',(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY to_jsonb(p)::text),'[]') FROM document_types.passages p),'passageVersions',(SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY to_jsonb(p)::text),'[]') FROM document_types.passage_versions p),'documentTypeAudit',(SELECT coalesce(jsonb_agg(to_jsonb(a) ORDER BY to_jsonb(a)::text),'[]') FROM document_types.command_audit a))"))
 def test_two_drafts_save_without_reservation_confirmation_winner_and_loser_whole_rollback(self):
  self.prepare_development();self.path();source=self.load('3')
  drafts=[self.doc(self.developed([source],['2']))['snapshot'] for _ in range(2)]
  stage=self.stage(source);self.assertEqual(stage['committed'],'0');self.assertEqual(Decimal(stage['plannedNotReserved']),Decimal('4'));self.assertEqual(Decimal(stage['residual']),Decimal('3'))
  self.assertTrue(all(self.read(d['id'])['ledger']==[] for d in drafts));self.assertEqual(self.balance(),'3.000000')
  commands=[self.confirm(d) for d in drafts]
  results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement(c),'app') for c in commands])
  self.assertEqual(sorted(r['state'] for r in results),['applied','insufficient_residual'])
  self.assertEqual(sorted(self.read(d['id'])['detail']['state'] for d in drafts),['Confirmed','Draft']);self.assertEqual(Decimal(self.stage(source)['residual']),Decimal('1'));self.assertEqual(self.balance(),'3.000000')
  loser=next(c for c,r in zip(commands,results) if r['state']=='insufficient_residual');before=self.owned_facts();self.assertEqual(self.doc(loser),dict(state='insufficient_residual'));self.assertEqual(self.owned_facts(),before)
 def test_partial_capacity_independent_passage_and_new_command_cannot_reset(self):
  self.prepare_development();self.path();self.path(destination='Unload');source=self.load('3')
  a=self.doc(self.developed([source],['2']))['snapshot'];c=self.confirm(a);self.assertEqual(self.doc(c)['state'],'applied')
  b=self.doc(self.developed([source],['2']))['snapshot'];self.assertEqual(self.doc(self.confirm(b))['state'],'insufficient_residual')
  independent=self.doc(self.developed([source],['3'],effect='Unload'))['snapshot'];self.assertEqual(self.doc(self.confirm(independent))['state'],'applied');self.assertEqual(self.balance(),'0.000000');self.assertEqual(Decimal(self.stage(source,'Unload')['residual']),0)
  self.assertEqual(self.doc(dict(c,commandId=uid()))['state'],'already_confirmed');self.assertEqual(self.doc(c)['state'],'replayed')
 def test_disable_reenable_and_rule_new_revision_do_not_reset_passage(self):
  self.prepare_development();self.path();source=self.load('3');a=self.doc(self.developed([source],['2']))['snapshot'];self.doc(self.confirm(a));b=self.doc(self.developed([source],['2']))['snapshot']
  self.assertEqual(self.path(enabled=False,revision=1)['state'],'applied');before=self.owned_facts();self.assertEqual(self.doc(self.confirm(b))['state'],'path_forbidden');self.assertEqual(self.owned_facts(),before)
  self.assertEqual(self.path(enabled=True,revision=2)['snapshot']['revision'],3);self.assertEqual(Decimal(self.stage(source)['residual']),1)
  self.assertEqual(self.doc(self.confirm(b))['state'],'config_changed')
  p=self.developed([source],['2'],documentId=b['id'],expectedRevision=b['revision'],operation='develop-save');p['lines'][0]['id']=b['lines'][0]['id'];p['lines'][0]['origins'][0]['expectedPathRevision']=3
  updated=self.doc(p);self.assertEqual(updated['state'],'applied');self.assertEqual(self.doc(self.confirm(updated['snapshot']))['state'],'insufficient_residual')
 def test_merged_multi_origin_and_walkable_multi_hop(self):
  self.prepare_development();self.path();self.path(source='None',destination='Transfer');a=self.load('3');b=self.load('4')
  draft=self.doc(self.developed([a,b],['1.000001','2.999999'],merged=True))['snapshot'];self.assertEqual(len(draft['lines']),1);self.assertEqual(len(draft['lines'][0]['origins']),2);self.assertEqual(draft['lines'][0]['quantity'],'4.000000')
  confirmed=self.doc(self.confirm(draft))['snapshot'];next_draft=self.doc(self.developed([confirmed],['2'],effect='Transfer'))['snapshot'];final=self.doc(self.confirm(next_draft))['snapshot']
  immediate=final['lines'][0]['origins'][0];self.assertEqual(immediate['sourceDocumentId'],confirmed['id']);self.assertEqual(len(self.read(immediate['sourceDocumentId'])['detail']['lines'][0]['origins']),2)
  self.assertEqual(Decimal(self.stage(a)['residual']),Decimal('1.999999'));self.assertEqual(Decimal(self.stage(b)['residual']),Decimal('1.000001'))
 def test_different_source_types_one_destination_and_forbidden_path_reject_whole(self):
  self.prepare_development();self.path();self.path(source='None');a=self.load('3');b=self.confirmed_none('4')
  draft=self.doc(self.developed([a,b],['1','2'],merged=True))['snapshot'];self.assertEqual(len(draft['lines'][0]['origins']),2)
  self.path(source='None',enabled=False,revision=1);before=self.owned_facts();self.assertEqual(self.doc(self.confirm(draft))['state'],'path_forbidden');self.assertEqual(self.owned_facts(),before);self.assertEqual(self.read(draft['id'])['detail']['state'],'Draft')
  self.path(source='None',enabled=True,revision=2);p=self.developed([a,b],['1','2'],merged=True);p['lines'][0]['origins'][1]['expectedPathRevision']=3
  d=self.doc(p)['snapshot'];self.assertEqual(self.doc(self.confirm(d))['state'],'applied')
 def test_unconfirmed_source_and_cross_company_or_tenant_not_admitted(self):
  self.prepare_development();self.path();draft=self.doc(self.draft())['snapshot'];before=self.owned_facts();self.assertEqual(self.doc(self.developed([draft]))['state'],'source_not_confirmed');self.assertEqual(self.owned_facts(),before)
  a=self.load();p=self.developed([a]);p['lines'][0]['origins'][0]['sourceDocumentId']=uid();self.assertEqual(self.doc(p)['state'],'forbidden');p=self.developed([a],tenantId=uid());self.assertEqual(self.doc(p)['state'],'invalid')
 def test_ordinary_save_cannot_strip_or_arbitrarily_change_backed_lines(self):
  self.prepare_development();self.path();a=self.load();p=self.developed([a],['2']);d=self.doc(p)['snapshot'];before=self.owned_facts()
  ordinary=dict(p,commandId=uid(),operation='save',documentId=d['id'],expectedRevision=1);ordinary['lines']=[{k:v for k,v in l.items() if k!='origins'} for l in p['lines']];ordinary['lines'][0]['quantity']='3'
  self.assertEqual(self.doc(ordinary)['state'],'development_plan_required');self.assertEqual(self.owned_facts(),before)
  remove=dict(p,commandId=uid(),operation='develop-save',documentId=d['id'],expectedRevision=1);remove['lines']=[dict(p['lines'][0],origins=[])];self.assertEqual(self.doc(remove)['state'],'origin_quantity_mismatch')
 def test_partial_draft_correction_remove_origin_and_quantity_has_no_capacity_effect(self):
  self.prepare_development();self.path();a=self.load('3');b=self.load('4');p=self.developed([a,b],['1','2'],merged=True);d=self.doc(p)['snapshot'];before=self.balance()
  corrected=dict(p,commandId=uid(),operation='develop-save',documentId=d['id'],expectedRevision=1);corrected['lines']=[dict(p['lines'][0],quantity='0.5',origins=[self.origin(a,'0.5')])];saved=self.doc(corrected)['snapshot']
  self.assertEqual(saved['lines'][0]['id'],d['lines'][0]['id']);self.assertEqual(saved['lines'][0]['quantity'],'0.500000');self.assertEqual(len(saved['lines'][0]['origins']),1);self.assertEqual(self.balance(),before);self.assertEqual(Decimal(self.stage(a)['residual']),3);self.assertEqual(Decimal(self.stage(b)['plannedNotReserved']),0)
 def test_none_effect_commits_capacity_service_never_stock(self):
  self.prepare_development();self.path(source='None');source=self.confirmed_none('2',self.service);draft=self.doc(self.developed([source],['2']))['snapshot'];confirmed=self.doc(self.confirm(draft))['snapshot'];self.assertEqual(self.read(confirmed['id'])['ledger'],[]);self.assertEqual(Decimal(self.stage(source)['residual']),0);self.assertEqual(self.sql('SELECT count(*) FROM documents.balances'),'0')
 def test_snapshot_compatibility_and_catalog_edit_preserves_old_origin(self):
  self.prepare_development();self.path();a=self.load('2');self.sql(f'''UPDATE catalog.items SET "Version"=2,"Label"='Changed canonical' WHERE "Id"='{self.part}' ''')
  draft=self.doc(self.developed([a],['1']))['snapshot'];self.assertEqual(draft['lines'][0]['label'],a['lines'][0]['label']);self.assertEqual(draft['lines'][0]['catalogRevision'],1)
  b=self.doc(self.draft(lines=[self.line('2',catalogRevision=2,warehouse=self.warehouse)]))['snapshot'];b=self.doc(self.confirm(b))['snapshot'];before=self.owned_facts();self.assertEqual(self.doc(self.developed([a,b],merged=True))['state'],'incompatible_origins');self.assertEqual(self.owned_facts(),before)
 def test_current_source_permission_before_effect_and_replay_no_origin_details_leak(self):
  self.prepare_development();self.path();a=self.load();p=self.developed([a]);d=self.doc(p)['snapshot'];c=self.confirm(d);self.doc(c)
  permission=next((q,s) for q,s in self.permissions if q['action']=='documents.develop');q,s=permission
  self.role_command(dict(q,commandId=uid(),resourceId=s['resourceId'],expectedRevision=1,action='documents.read'))
  before=self.owned_facts();self.assertEqual(self.doc(c)['state'],'forbidden');self.assertEqual(self.doc(p)['state'],'forbidden');self.assertEqual(self.owned_facts(),before)
 def test_duplicate_origins_q6_and_target_aggregate_bounds(self):
  self.prepare_development();self.path();a=self.load('2')
  for q in ['0','-1','01','1e0','1,0','1.0000001','1000000000000000000','NaN']:
   p=self.developed([a]);p['lines'][0]['origins'][0]['quantity']=q;self.assertEqual(self.doc(p)['state'],'invalid',q)
  p=self.developed([a]);p['lines'][0]['origins']*=2;p['lines'][0]['quantity']='2';self.assertEqual(self.doc(p)['state'],'invalid')
  p=self.developed([a]);p['lines'][0]['quantity']='2';self.assertEqual(self.doc(p)['state'],'origin_quantity_mismatch')
  p=self.developed([a]);p['lines'][0]['origins']=[self.origin(a)]*201;self.assertEqual(self.doc(p)['state'],'invalid')
 def test_exact_retry_canonicalizes_origin_quantities_without_reconsumption(self):
  self.prepare_development();self.path();a=self.load();p=self.developed([a],['1.0']);result=self.doc(p);p['lines'][0]['origins'][0]['quantity']='1.000000';p['lines'][0]['quantity']='1';self.assertEqual(self.doc(p),dict(state='replayed',snapshot=result['snapshot']))
  c=self.confirm(result['snapshot']);accepted=self.doc(c);before=self.owned_facts();self.assertEqual(self.doc(c),dict(state='replayed',snapshot=accepted['snapshot']));self.assertEqual(self.owned_facts(),before)
  self.path(enabled=False,revision=1);self.assertEqual(self.doc(c)['state'],'replayed');self.assertEqual(self.doc(p)['state'],'replayed')
 def test_insertion_and_deferred_commit_audit_failure_rollback_capacity_stock_header(self):
  self.prepare_development();self.path(destination='Unload');a=self.load('5');draft=self.doc(self.developed([a],['2'],effect='Unload'))['snapshot'];command=self.confirm(draft);before=self.owned_facts()
  self.sql("CREATE FUNCTION documents.fixture_mvp08_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic MVP08 atomic rollback'; END $$")
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  for table,event in [('command_audit','INSERT'),('versions','INSERT'),('ledger','INSERT'),('headers','UPDATE'),('balances','UPDATE')]:
   for deferred in (False,True):
    sql=('CREATE CONSTRAINT TRIGGER mvp08_fail AFTER ' if deferred else 'CREATE TRIGGER mvp08_fail BEFORE ')+event+' ON documents.'+table+(' DEFERRABLE INITIALLY DEFERRED' if deferred else '')+' FOR EACH ROW EXECUTE FUNCTION documents.fixture_mvp08_fail()';self.sql(sql)
    try:
     result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.statement(command)+'COMMIT;',env=env,text=True,capture_output=True,timeout=20);self.assertNotEqual(result.returncode,0);self.assertIn('synthetic MVP08 atomic rollback',result.stderr);self.assertEqual(self.owned_facts(),before)
    finally:self.sql('DROP TRIGGER mvp08_fail ON documents.'+table)
  self.assertEqual(self.doc(command)['state'],'applied');self.assertEqual(Decimal(self.stage(a,'Unload')['residual']),3)
 def test_exact_new_action_scopes_and_no_admin_implicit_development(self):
  self.prepare_development()
  for action,c,s,w in [('documents.develop',self.company,None,None),('documents.develop',self.company,self.site,self.warehouse),('document-types.paths.manage',None,None,None),('document-types.paths.manage',self.company,self.site,None),('documents.develop.*',self.company,self.site,None)]:
   self.assertIn(self.role_command(self.role_payload('permission',label='Invalid',action=action,legalEntityId=c,siteId=s,warehouseId=w))['state'],('invalid','forbidden'))
  self.assertIn('documents.develop',self.role_read()['actions']);self.assertIn('document-types.paths.manage',self.role_read()['actions'])
 def test_confirmed_allocations_and_rule_facts_immutable_no_direct_app_acl(self):
  self.prepare_development();self.path();a=self.load();draft=self.doc(self.developed([a]))['snapshot'];self.doc(self.confirm(draft))
  for table in ('document_types.passages','document_types.passage_versions','documents.origins'):
   self.assertEqual(self.sql(f"SELECT has_table_privilege('{os.environ['R00_APP_USER']}','{table}','SELECT,INSERT,UPDATE,DELETE,TRUNCATE')"),'f')
  settings='BEGIN;SELECT set_config(\'app.tenant_id\','+lit(self.tenant)+',true),set_config(\'app.legal_entity_id\','+lit(self.company)+',true);'
  for change in ['UPDATE documents.origins SET "Quantity"=0.5','DELETE FROM documents.origins','UPDATE document_types.passage_versions SET "Enabled"=false']:
   self.assertNotEqual(self.owner_sql(settings+change+';COMMIT;',ok=False).returncode,0)

 def additional_site(self):
  actor=self.actor;self.actor=self.owner_actor;site=self.create_site(self.tenant,self.company);warehouse=self.org_command(self.org_payload(kind='warehouse',tenantId=self.tenant,parentId=site,name='Fresh destination warehouse'),self.tenant)['snapshot']['resourceId'];self.actor=actor
  for action in ('documents.read','documents.save','documents.confirm','documents.develop','inventory.document-effects.apply','inventory.quantities.read'):
   q=self.role_payload('permission',label=action+site,action=action,legalEntityId=self.company,siteId=site,warehouseId=warehouse if action.startswith('inventory.') else None);reply=self.role_command(q);self.assertEqual(reply['state'],'applied');self.permissions.append((q,reply['snapshot']))
  self.update_role();return site,warehouse
 def test_cross_site_same_company_explicit_rule_fresh_operational_warehouse_not_history(self):
  self.prepare_development();source=self.load('3');self.path(destination='Load');source_site=self.site;source_wh=self.warehouse;target_site,target_wh=self.additional_site();self.site=target_site;self.warehouse=target_wh
  proposed=self.developed([source],['1'],effect='Load');before=self.owned_facts();self.assertEqual(self.doc(proposed)['state'],'path_forbidden');self.assertEqual(self.owned_facts(),before)
  self.assertEqual(self.path(destination='Load',revision=1,cross=True)['state'],'applied');proposed['lines'][0]['origins'][0]['expectedPathRevision']=2
  foreign=dict(proposed,commandId=uid(),lines=[dict(proposed['lines'][0],warehouseId=source_wh)]);self.assertEqual(self.doc(foreign)['state'],'forbidden')
  draft=self.doc(proposed)['snapshot'];self.assertEqual(draft['siteId'],target_site);self.assertEqual(draft['lines'][0]['warehouseId'],target_wh);self.assertEqual(draft['lines'][0]['origins'][0]['source']['warehouseId'],source_wh);self.assertEqual(draft['lines'][0]['origins'][0]['source']['siteId'],source_site)
  self.assertEqual(self.doc(self.confirm(draft))['state'],'applied');self.assertEqual(self.balance(),'1.000000');self.site=source_site;self.warehouse=source_wh;self.assertEqual(self.balance(),'3.000000')
 def test_each_source_permission_revocation_both_physical_orders_and_replay(self):
  self.prepare_development();a=self.load('20');source_site=self.site;source_wh=self.warehouse;other_site,other_wh=self.additional_site();self.site=other_site;self.warehouse=other_wh;b=self.load('20');self.site=source_site;self.warehouse=source_wh;self.path(cross=True)
  for source_scope in (source_site,other_site):
   q,s=next((q,s) for q,s in self.permissions if q['action']=='documents.develop' and q['siteId']==source_scope)
   for physical_first in ('revoke','effect'):
    draft=self.doc(self.developed([a,b],['1','1'],merged=True))['snapshot'];command=self.confirm(draft);before=self.balance()
    revoke='SELECT pg_advisory_xact_lock(777036);UPDATE organization_access.tenant_role_objects SET "Data"="Data"-\'siteId\' WHERE "Id"='+lit(s['resourceId'])+";SELECT jsonb_build_object('state','revoked');"
    restore='UPDATE organization_access.tenant_role_objects SET "Data"='+lit(json.dumps(s))+'::jsonb WHERE "Id"='+lit(s['resourceId'])
    if physical_first=='revoke':
     results,holder=self.barrier_race(revoke,[(self.statement(command),'app')],holder_role='infra');self.assertEqual(results,[dict(state='forbidden')]);self.assertEqual(self.read(draft['id'])['detail']['state'],'Draft')
    else:
     results,holder=self.barrier_race(self.statement(command),[(revoke,'infra')],holder_role='app');self.assertEqual(holder[-1]['state'],'applied');self.assertEqual(results,[dict(state='revoked')]);self.assertEqual(self.doc(command)['state'],'forbidden')
    self.sql(restore);self.assertEqual(self.balance(),before)
    if physical_first=='effect':self.assertEqual(self.doc(command)['state'],'replayed')
 def test_rr_old_snapshot_path_change_and_source_permission_change_fail_closed(self):
  import selectors
  self.prepare_development();self.path();a=self.load();draft=self.doc(self.developed([a]))['snapshot'];command=self.confirm(draft)
  for change in ('path','permission'):
   env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD']);child=subprocess.Popen(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env,text=True)
   try:
    child.stdin.write("BEGIN ISOLATION LEVEL REPEATABLE READ;SELECT 'SNAPSHOT_READY',count(*) FROM pg_catalog.pg_class;\n");child.stdin.flush();poll=selectors.DefaultSelector();poll.register(child.stdout,selectors.EVENT_READ)
    try:self.assertTrue(poll.select(10));self.assertTrue(child.stdout.readline().startswith('SNAPSHOT_READY|'))
    finally:poll.close()
    if change=='path':self.assertEqual(self.path(revision=1,cross=True)['state'],'applied')
    else:
     q,s=next((q,s) for q,s in self.permissions if q['action']=='documents.develop');self.role_command(dict(q,commandId=uid(),resourceId=s['resourceId'],expectedRevision=1,action='documents.read'))
    child.stdin.write(self.statement(command)+'COMMIT;\n');child.stdin.flush();child.stdin.close();child.stdin=None;output,error=child.communicate(timeout=20);self.assertNotEqual(child.returncode,0);self.assertIn('could not serialize',error)
   finally:
    if child.poll() is None:child.kill();child.communicate(timeout=5)
  self.assertEqual(self.read(draft['id'])['detail']['state'],'Draft')
 def test_multi_source_excess_from_one_stage_rolls_back_every_other_stage_and_stock(self):
  self.prepare_development();self.path(destination='Unload');a=self.load('3');b=self.load('3');first=self.doc(self.developed([a],['3'],effect='Unload'))['snapshot'];self.doc(self.confirm(first));draft=self.doc(self.developed([a,b],['1','1'],effect='Unload',merged=True))['snapshot'];before=self.owned_facts();self.assertEqual(self.doc(self.confirm(draft))['state'],'insufficient_residual');self.assertEqual(self.owned_facts(),before);self.assertEqual(Decimal(self.stage(b,'Unload')['residual']),3)
 def test_rule_change_and_destination_confirmation_serialize_in_both_orders(self):
  self.prepare_development();self.path();a=self.load('10')
  def statement(enabled,revision):return self.actor_settings()+'SELECT document_types.command('+lit(json.dumps(dict(commandId=uid(),operation='path',legalEntityId=self.company,sourceTypeId=self.types['Load']['id'],destinationTypeId=self.types['None']['id'],expectedRevision=revision,enabled=enabled,allowCrossSite=False)))+'::jsonb);'
  draft=self.doc(self.developed([a]))['snapshot'];command=self.confirm(draft);results,holder=self.barrier_race(statement(False,1),[(self.statement(command),'app')]);self.assertEqual(holder[-1]['state'],'applied');self.assertEqual(results,[dict(state='path_forbidden')])
  self.path(revision=2);payload=self.developed([a]);payload['lines'][0]['origins'][0]['expectedPathRevision']=3;draft=self.doc(payload)['snapshot'];command=self.confirm(draft);results,holder=self.barrier_race(self.statement(command),[(statement(False,3),'app')],holder_role='app');self.assertEqual(holder[-1]['state'],'applied');self.assertEqual(results[0]['state'],'applied');self.assertEqual(self.doc(command)['state'],'replayed')

 def test_merged_target_overflow_is_exact_without_service_stock_effects(self):
  self.prepare_development();self.path(source='None');a=self.confirmed_none('999999999999999999.999999',self.service);b=self.confirmed_none('0.000001',self.service)
  payload=self.developed([a,b],['999999999999999999.999999','0.000001'],merged=True);payload['lines'][0]['quantity']='999999999999999999.999999';before=self.owned_facts();self.assertEqual(self.doc(payload)['state'],'quantity_overflow');self.assertEqual(self.owned_facts(),before);self.assertEqual(self.sql('SELECT count(*) FROM documents.ledger'),'0')
 def test_draft_origin_insert_and_path_audit_insert_deferred_failure_roll_back(self):
  self.prepare_development();self.path();a=self.load();payload=self.developed([a]);before=self.owned_facts();self.sql("CREATE FUNCTION documents.fixture_plan_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic planned origin rollback'; END $$")
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  for deferred in (False,True):
   create=('CREATE CONSTRAINT TRIGGER plan_fail AFTER INSERT' if deferred else 'CREATE TRIGGER plan_fail BEFORE INSERT')+' ON documents.origins'+(' DEFERRABLE INITIALLY DEFERRED' if deferred else '')+' FOR EACH ROW EXECUTE FUNCTION documents.fixture_plan_fail()';self.sql(create)
   try:
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.statement(payload)+'COMMIT;',env=env,text=True,capture_output=True,timeout=20);self.assertNotEqual(result.returncode,0);self.assertIn('synthetic planned origin rollback',result.stderr);self.assertEqual(self.owned_facts(),before)
   finally:self.sql('DROP TRIGGER plan_fail ON documents.origins')
  for deferred in (False,True):
   create=('CREATE CONSTRAINT TRIGGER plan_fail AFTER INSERT' if deferred else 'CREATE TRIGGER plan_fail BEFORE INSERT')+' ON document_types.command_audit'+(' DEFERRABLE INITIALLY DEFERRED' if deferred else '')+' FOR EACH ROW EXECUTE FUNCTION documents.fixture_plan_fail()';self.sql(create)
   request=dict(commandId=uid(),operation='path',legalEntityId=self.company,sourceTypeId=self.types['Load']['id'],destinationTypeId=self.types['None']['id'],expectedRevision=1,enabled=False,allowCrossSite=False)
   try:
    result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+self.actor_settings()+'SELECT document_types.command('+lit(json.dumps(request))+'::jsonb);COMMIT;',env=env,text=True,capture_output=True,timeout=20);self.assertNotEqual(result.returncode,0);self.assertEqual(self.owned_facts(),before)
   finally:self.sql('DROP TRIGGER plan_fail ON document_types.command_audit')

 def test_revoked_source_read_redacts_origin_details_and_quantity_read_is_not_source_access(self):
  self.prepare_development();a=self.load('3');target_site=self.site;target_wh=self.warehouse;other_site,other_wh=self.additional_site();self.site=other_site;self.warehouse=other_wh;b=self.load('3');self.site=target_site;self.warehouse=target_wh;self.path(cross=True)
  draft=self.doc(self.developed([a,b],['1','1'],merged=True))['snapshot'];command=self.confirm(draft);self.assertEqual(self.doc(command)['state'],'applied')
  request,snapshot=next((q,s) for q,s in self.permissions if q['action']=='documents.read' and q['siteId']==other_site);self.role_command(dict(request,commandId=uid(),resourceId=snapshot['resourceId'],expectedRevision=1,action='documents.save'))
  origins=self.read(draft['id'])['detail']['lines'][0]['origins'];restricted=[o for o in origins if o.get('restricted')];self.assertEqual(restricted,[dict(quantity='1.000000',restricted=True)]);self.assertEqual(len([o for o in origins if o.get('sourceDocumentId')==a['id']]),1);self.assertNotIn(b['id'],json.dumps(origins))
  self.assertEqual(self.doc(command)['state'],'forbidden');stock=self.read(warehouse=other_wh,site=other_site);self.assertEqual(stock['balances'][0]['quantity'],'3.000000');self.assertIsNone(stock['detail']);self.assertEqual(stock['stages'],[]);self.assertNotIn('sourceDocumentId',json.dumps(stock));self.assertEqual(self.read(b['id'],site=other_site)['state'],'forbidden')

 def test_actual_foreign_confirmed_sources_cannot_group_across_company_or_tenant(self):
  self.prepare_development();self.path();source=self.confirmed_none('3')
  for other_tenant in (False,True):
   tenant=uid() if other_tenant else self.tenant;company,site,item,type_id,document,line=[uid() for _ in range(6)]
   if other_tenant:self.sql(f"INSERT INTO organization_access.tenants VALUES('{tenant}','Synthetic foreign tenant')")
   self.sql(f'''BEGIN;
    INSERT INTO organization_access.legal_entities VALUES('{company}','{tenant}','Synthetic foreign company');
    INSERT INTO organization_access.sites VALUES('{site}','{company}','{tenant}','Synthetic foreign site');
    INSERT INTO catalog.items VALUES('{item}','{tenant}','{company}','Service','Synthetic foreign service',1);
    INSERT INTO document_types.definitions VALUES('{type_id}','{tenant}','{company}',1);
    INSERT INTO document_types.versions("TenantId","LegalEntityId","DocumentTypeId","Revision","Label","Effect") VALUES('{tenant}','{company}','{type_id}',1,'Synthetic foreign type','None');
    INSERT INTO documents.headers VALUES('{document}','{tenant}','{company}','{site}','{type_id}',1,'Draft','Synthetic foreign source',NULL,NULL);
    INSERT INTO documents.lines VALUES('{tenant}','{company}','{document}','{line}',1,'{item}',1,'Service','Synthetic foreign service',3,NULL,NULL);
    UPDATE documents.headers SET "State"='Confirmed',"Revision"=2,"AppliedConfiguration"=jsonb_build_object('documentType',jsonb_build_object('id','{type_id}','revision',1,'effect','None'),'policy',jsonb_build_object('revision',0,'allowNegative',false)),"ConfirmedAt"=clock_timestamp() WHERE "Id"='{document}';
    COMMIT;''')
   self.assertEqual(self.sql(f'''SELECT "State" FROM documents.headers WHERE "TenantId"='{tenant}' AND "LegalEntityId"='{company}' AND "Id"='{document}' '''),'Confirmed')
   proposed=self.developed([source],['1']);proposed['lines'].append(dict(id=uid(),itemId=item,catalogRevision=1,quantity='1',warehouseId=None,destinationWarehouseId=None,origins=[dict(sourceDocumentId=document,sourceLineId=line,quantity='1',expectedPathRevision=1)]))
   before=self.owned_facts();self.assertEqual(self.doc(proposed),dict(state='forbidden'));self.assertEqual(self.owned_facts(),before)
   self.assertEqual(self.read(document),dict(state='not_found'))
 def test_opposing_multi_source_transfers_have_distinct_waiters_and_one_whole_commit(self):
  self.prepare_development();self.path(destination='Transfer');a=self.load('3');b=self.load('3',warehouse=self.destination)
  drafts=[]
  for sources in ([a,b],[b,a]):
   payload=self.developed(sources,['2','2'],effect='Transfer')
   for target,src in zip(payload['lines'],sources):
    target['warehouseId']=src['lines'][0]['warehouseId'];target['destinationWarehouseId']=self.destination if target['warehouseId']==self.warehouse else self.warehouse
   drafts.append(self.doc(payload)['snapshot'])
  commands=[self.confirm(d) for d in drafts];results,_=self.barrier_race('SELECT pg_advisory_xact_lock(777036);',[(self.statement(c),'app') for c in commands])
  self.assertEqual(sorted(r['state'] for r in results),['applied','insufficient_residual'])
  self.assertEqual(self.balance(),'3.000000');self.assertEqual(self.balance(self.destination),'3.000000')
  for source in (a,b):self.assertEqual(Decimal(self.stage(source,'Transfer')['residual']),1)
  for draft,result in zip(drafts,results):
   current=self.read(draft['id']);self.assertEqual(current['detail']['state'],'Confirmed' if result['state']=='applied' else 'Draft');self.assertEqual(len(current['ledger']),4 if result['state']=='applied' else 0)
  before=self.owned_facts();loser=next(c for c,r in zip(commands,results) if r['state']=='insufficient_residual');self.assertEqual(self.doc(loser),dict(state='insufficient_residual'));self.assertEqual(self.owned_facts(),before)
 def test_develop_and_develop_save_audit_failure_and_new_path_commit_failure_are_atomic(self):
  self.prepare_development();self.path();a=self.load('3');payload=self.developed([a],['2']);draft=self.doc(payload)['snapshot']
  corrected=self.developed([a],['1'],operation='develop-save',documentId=draft['id'],expectedRevision=1);corrected['lines'][0]['id']=draft['lines'][0]['id']
  env=dict(os.environ,PGDATABASE=self.database,PGUSER=os.environ['R00_APP_USER'],PGPASSWORD=os.environ['R00_APP_PASSWORD'])
  self.sql("CREATE FUNCTION documents.fixture_whole_audit_fail() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic whole mutation audit rollback'; END $$")
  for table in ('documents.command_audit','document_types.command_audit'):
   for deferred in (False,True):
    trigger=('CREATE CONSTRAINT TRIGGER whole_fail AFTER INSERT' if deferred else 'CREATE TRIGGER whole_fail BEFORE INSERT')+' ON '+table+(' DEFERRABLE INITIALLY DEFERRED' if deferred else '')+' FOR EACH ROW EXECUTE FUNCTION documents.fixture_whole_audit_fail()';self.sql(trigger)
    try:
     requests=[self.developed([a],['1']),corrected] if table=='documents.command_audit' else [dict(commandId=uid(),operation='path',legalEntityId=self.company,sourceTypeId=self.types['Load']['id'],destinationTypeId=self.types['Unload']['id'],expectedRevision=0,enabled=True,allowCrossSite=False)]
     for request in requests:
      before=self.owned_facts();statement=self.statement(request) if table=='documents.command_audit' else self.actor_settings()+'SELECT document_types.command('+lit(json.dumps(request))+'::jsonb);'
      result=subprocess.run(['psql','-X','-qAt','-v','ON_ERROR_STOP=1'],input='BEGIN;'+statement+'COMMIT;',env=env,text=True,capture_output=True,timeout=20)
      self.assertNotEqual(result.returncode,0);self.assertIn('synthetic whole mutation audit rollback',result.stderr);self.assertEqual(self.owned_facts(),before)
    finally:self.sql('DROP TRIGGER whole_fail ON '+table)

if __name__=='__main__':unittest.main()
