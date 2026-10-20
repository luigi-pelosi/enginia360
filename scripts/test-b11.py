#!/usr/bin/env python3
"""B11 continuity probes against real identity/API/database and faulting receiver."""
import importlib.util
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('b10', Path(__file__).with_name('test-b10.py'))
assert spec and spec.loader
b10 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b10)


def uncertain():
    order, summary, closure, saved = b10.closed_and_requested('lost-response')
    result = b10.wait(order, lambda x: x['status'] == 'Confirmed')
    [remote] = b10.received(saved['id'])
    assert remote['posts'] == 1, ('uncertain response must be reconciled by status lookup before any resubmission', remote['posts'], remote['statusQueries'])
    assert remote['statusQueries'] >= 1
    assert result['summary'] == summary and result['externalReference'] == remote['externalReference']
    assert b10.state(order)[1]['technicalClosure'] == closure
    assert b10.close_administratively(order)[0] == 201
    print('PASS B11 lost response after business effect: status-first reconciliation, one POST, stable reference and source preserved')


def bounded():
    import time
    order, summary, closure, saved = b10.closed_and_requested('unavailable')
    current = b10.wait(order, lambda x: x['delivery']['state'] == 'NeedsReconciliation', seconds=12)
    assert current['status'] == 'Pending' and current['externalReference'] is None
    assert current['delivery']['nextAttemptAt'] is None
    assert current['delivery']['failures'] == 4
    before = current['delivery']
    time.sleep(2)
    assert b10.history(order)[1][0]['delivery'] == before, 'exhausted automatic recovery must stop until explicit authorized reconciliation'
    assert b10.close_administratively(order)[0] == 409
    assert b10.state(order)[1]['technicalClosure'] == closure
    print('PASS B11 bounded exponential backoff escalates without losing request or fabricating confirmation')
    return order, summary, closure, saved


def reconcile():
    import uuid
    order, summary, closure, saved = bounded()
    b10.mode('complete')
    path = b10.order_path(order) + '/administrative-requests/' + saved['id'] + '/reconciliation'
    command = {'id': str(uuid.uuid4())}
    status, result = b10.b.call(path, method='POST', payload=command)
    assert status == 202, ('authorized scoped reconciliation must durably schedule status-first recovery', status, result)
    confirmed = b10.wait(order, lambda x: x['status'] == 'Confirmed')
    assert confirmed['summary'] == summary
    assert b10.b.call(path, method='POST', payload=command)[0] == 200, 'exact reconciliation retry is idempotent'
    assert b10.received(saved['id'])[0]['posts'] == 1, 'resubmit only after definitive NotFound, preserving stable request identity'
    assert b10.close_administratively(order)[0] == 201
    print('PASS B11 authorized idempotent reconciliation after outage recovers original queued request without false confirmation')


def fairness():
    requests=[]
    for _ in range(20):
        order,_,_,_=b10.closed_and_requested('unavailable')
        requests.append(order)
    for order in requests:
        b10.wait(order,lambda x:x['delivery']['state']=='NeedsReconciliation',seconds=12)
    order,summary,_,saved=b10.closed_and_requested('complete')
    current=b10.wait(order,lambda x:x['status']=='Confirmed',seconds=8)
    assert current['summary']==summary and b10.received(saved['id'])[0]['posts']==1
    print('PASS B11 twenty escalated older requests cannot starve newer authorized work; fair bounded envelope scanning')


def recovery_prepare():
    import json
    order, summary, closure, saved = bounded()
    b10.state_file().write_text(json.dumps(dict(order=order, summary=summary, closure=closure, saved=saved)))


def recovery_denied():
    import json, uuid
    fixture = json.loads(b10.state_file().read_text())
    order, saved = fixture['order'], fixture['saved']
    before = b10.history(order)
    path = b10.order_path(order) + '/administrative-requests/' + saved['id'] + '/reconciliation'
    assert b10.b.call(path, method='POST', payload={'id':str(uuid.uuid4())})[0] == 403
    assert b10.history(order) == before, 'denied recovery must not alter queued state or business facts'
    print('PASS B11 valid same-tenant membership lacking exact action/resource scope cannot reconcile')


def recovery_negatives():
    import json, uuid
    from concurrent.futures import ThreadPoolExecutor
    fixture = json.loads(b10.state_file().read_text())
    order, saved = fixture['order'], fixture['saved']
    path = b10.order_path(order) + '/administrative-requests/' + saved['id'] + '/reconciliation'
    beta = b10.b.b02.login(b10.b.BASE, 'operatore-beta-sintetico', 'synthetic-beta-password')
    assert b10.b.b02.request(b10.b.BASE+'/api/v1/workshop'+path,method='POST',payload={'id':str(uuid.uuid4())})[0]==401
    assert b10.b.call(path, token=beta, method='POST', payload={'id':str(uuid.uuid4())})[0] == 404
    assert b10.b.call(path, method='POST', payload={'id':str(uuid.UUID(int=0))})[0] == 400
    assert b10.b.call(path, method='POST', payload={'id':str(uuid.uuid4()), 'status':'Confirmed'})[0] == 400
    assert b10.b.call(path.replace(saved['id'],str(uuid.uuid4())), method='POST', payload={'id':str(uuid.uuid4())})[0] == 404
    b10.mode('complete')
    command={'id':str(uuid.uuid4())}
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(lambda _:b10.b.call(path, method='POST', payload=command)[0], range(8)))
    assert sorted(results)==[200]*7+[202], results
    done=b10.wait(order, lambda x:x['status']=='Confirmed')
    assert done['summary']==fixture['summary']
    assert b10.b.call(path, method='POST', payload={'id':str(uuid.uuid4())})[0]==409, 'a final outcome is not overwritten by recovery'
    rejected,_,_,rejected_request=b10.closed_and_requested('reject')
    b10.wait(rejected, lambda x:x['status']=='Rejected')
    rejection_path=b10.order_path(rejected)+'/administrative-requests/'+rejected_request['id']+'/reconciliation'
    assert b10.b.call(rejection_path, method='POST', payload={'id':str(uuid.uuid4())})[0]==409
    assert b10.received(rejected_request['id'])[0]['posts']==1
    print('PASS B11 cross-tenant/input/foreign-resource negatives; eight concurrent exact recoveries record one action; confirmed/refused outcomes cannot be fabricated or retried')


def restart_prepare():
    import json, time
    order, summary, closure, saved = b10.closed_and_requested('hold-response')
    deadline = time.monotonic() + 8
    while b10.sim('/control/inflight')[1]['requestId'] != saved['id']:
        assert time.monotonic() < deadline, 'receiver did not reach committed/inflight boundary'
        time.sleep(0.05)
    b10.state_file().write_text(json.dumps(dict(order=order, summary=summary, closure=closure, saved=saved)))
    print('PASS B11 receiver effect committed, sender response deliberately withheld: ready for real API process kill')


def completion_prepare():
    import json
    order,summary,closure,saved=b10.closed_and_requested('complete')
    result=b10.wait(order,lambda x:x['delivery']['state']=='Completed' and x['status']=='Pending')
    assert result['externalReference'] is None
    b10.state_file().write_text(json.dumps(dict(order=order,summary=summary,closure=closure,saved=saved)))
    assert b10.close_administratively(order)[0]==409
    print('PASS B11 connector completion durable while owner outcome commit fails; administrative closure still blocked')


def completion_verify():
    import json
    fixture=json.loads(b10.state_file().read_text())
    result=b10.wait(fixture['order'],lambda x:x['status']=='Confirmed',seconds=55)
    assert result['summary']==fixture['summary']
    assert b10.received(fixture['saved']['id'])[0]['posts']==1
    assert b10.state(fixture['order'])[1]['technicalClosure']==fixture['closure']
    print('PASS B11 restart after connector commit/before owner outcome: finish original business confirmation without resending')


def lease_verify():
    import json, time
    fixture=json.loads(b10.state_file().read_text())
    time.sleep(7)  # The original request now times out; it no longer owns the replaced lease.
    current=b10.history(fixture['order'])[1][0]
    assert current['delivery']['state']=='NeedsReconciliation' and current['delivery']['failures']==4, ('a stale worker must not overwrite a replacement lease/state',current['delivery'])
    print('PASS B11 lease fencing rejects late stale worker writes after another owner replaces the lease')


def restart_verify():
    import json
    fixture = json.loads(b10.state_file().read_text())
    result = b10.wait(fixture['order'], lambda x: x['status'] == 'Confirmed', seconds=55)
    [remote] = b10.received(fixture['saved']['id'])
    assert remote['posts'] == 1, ('restart after receiver commit must reconcile rather than repeat POST', remote['posts'])
    assert remote['statusQueries'] >= 1
    assert result['summary'] == fixture['summary'] and b10.state(fixture['order'])[1]['technicalClosure'] == fixture['closure']
    print('PASS B11 real process kill/restart during remote effect: persisted intent, lease expiry, status-first recovery, one receiver effect')


if __name__ == '__main__':
    b10.b.BASE = sys.argv[1]
    b10.b.alpha = b10.b.b02.login(b10.b.BASE, 'operatore-alfa-sintetico', 'synthetic-alpha-password')
    globals()[sys.argv[2]]()
