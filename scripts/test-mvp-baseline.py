#!/usr/bin/env python3
"""Offline D96 authorization/backlog guards; no runtime-conformance claim."""
import copy
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = {'identity', 'organization', 'counterparties', 'catalog', 'inventory',
           'document-types', 'documents'}


def current_block(text, *, require_routine=True):
    start, end = '<!-- mvp-current:start -->', '<!-- mvp-current:end -->'
    assert text.count(start) == text.count(end) == 1, 'one current MVP policy block required'
    assert text.index(start) < text.index(end), 'reversed current policy markers'
    block = text.split(start)[1].split(end)[0]
    assert 'D96' in block, 'current D96 authorization missing'
    assert 'mvp-delivery-plan.md' in block, 'current delivery plan missing'
    assert 'mvp-backlog.json' in block, 'current machine-readable backlog missing'
    if require_routine:
        assert 'full_architecture=false' in block, 'offline/targeted verification boundary missing'
    return block


def validate_backlog(data):
    assert isinstance(data, dict), 'backlog must be an object'
    assert type(data.get('schemaVersion')) is int and data['schemaVersion'] == 1, 'schema version'
    assert data.get('authorization') == 'D96', 'backlog authorization'
    domains = data.get('domainIds')
    assert isinstance(domains, list) and all(isinstance(d, str) for d in domains), 'domain IDs'
    assert len(domains) == len(DOMAINS) and set(domains) == DOMAINS, 'exact seven-domain MVP'
    items = data.get('items')
    assert isinstance(items, list) and items, 'active MVP backlog missing'
    ids = []
    for item in items:
        assert isinstance(item, dict), 'item must be an object'
        assert isinstance(item.get('id'), str) and item['id'].strip(), 'item ID'
        ids.append(item['id'])
        assert isinstance(item.get('title'), str) and item['title'].strip(), 'item title'
        assert isinstance(item.get('domainIds'), list) and item['domainIds'], 'item domain coverage'
        assert all(isinstance(d, str) and d in DOMAINS for d in item['domainIds']), 'unknown item domain'
        assert len(set(item['domainIds'])) == len(item['domainIds']), 'duplicate item domain'
        deps = item.get('dependsOn')
        assert isinstance(deps, list) and all(isinstance(d, str) for d in deps), 'dependencies'
        assert len(set(deps)) == len(deps), 'duplicate dependency'
        assert item.get('status') in {'ready', 'backlog', 'in_progress', 'done'}, 'status'
        acceptance = item.get('acceptance')
        assert isinstance(acceptance, list) and acceptance and all(isinstance(a, str) and a.strip() for a in acceptance), 'executable acceptance contract missing'
        assert 'issueNumber' in item and (item['issueNumber'] is None or (type(item['issueNumber']) is int and item['issueNumber'] > 0)), 'issue reference'
    assert len(ids) == len(set(ids)), 'duplicate item IDs'
    by_id = {item['id']: item for item in items}
    assert set().union(*(set(i['domainIds']) for i in items)) == DOMAINS, 'incomplete domain coverage'
    assert sum(i['status'] == 'in_progress' for i in items) <= 1, 'WIP1 exceeded'
    assert any(i['status'] in {'ready', 'in_progress'} for i in items), 'no actionable MVP plan'
    visiting, visited = set(), set()

    def visit(identifier):
        assert identifier in by_id, 'missing dependency'
        assert identifier not in visiting, 'cyclic dependency'
        if identifier in visited:
            return
        visiting.add(identifier)
        item = by_id[identifier]
        for dependency in item['dependsOn']:
            visit(dependency)
            if item['status'] in {'in_progress', 'done'}:
                assert by_id[dependency]['status'] == 'done', 'unfinished dependency of active/done item'
        visiting.remove(identifier)
        visited.add(identifier)

    for identifier in ids:
        visit(identifier)


def validate_repository(root):
    for relative in ('AGENTS.md', 'docs/productization-plan.md'):
        # The archived roadmap redirects authority; CI policy lives in AGENTS/active plan.
        current_block((root / relative).read_text(), require_routine=relative == 'AGENTS.md')
    charter = (root / 'PROJECT_CHARTER.md').read_text()
    assert re.search(r'^#{2,4} .*D96\b', charter, re.M), 'charter D96 authorization section missing'
    plan = root / 'docs/mvp-delivery-plan.md'
    assert plan.is_file(), 'active MVP delivery plan missing'
    text = plan.read_text()
    assert 'D96' in text and 'mvp-backlog.json' in text, 'plan authorization/backlog linkage'
    assert re.search(r'WIP\s*=?\s*1', text, re.I), 'WIP1 policy missing'
    assert 'full_architecture=false' in text, 'routine full architecture forbidden'
    for relative in ('docs/mvp-baseline.md', 'docs/mvp-existing-code-assessment.md'):
        assert (root / relative).is_file(), 'MVP source evidence missing'
    validate_backlog(json.loads((root / 'docs/mvp-backlog.json').read_text()))


class MvpBaselineTests(unittest.TestCase):
    def test_current_authorization_and_active_plan(self):
        validate_repository(ROOT)

    def test_backlog_mutations_fail_closed(self):
        path = ROOT / 'docs/mvp-backlog.json'
        self.assertTrue(path.is_file(), 'active MVP backlog missing')
        original = json.loads(path.read_text())
        validate_backlog(original)
        mutations = [
            lambda d: d.update(authorization='D95'),
            lambda d: d.update(schemaVersion=True),
            lambda d: d['domainIds'].pop(),
            lambda d: d['domainIds'].append('unknown'),
            lambda d: d['items'].append(copy.deepcopy(d['items'][0])),
            lambda d: d['items'][0].update(dependsOn=['missing']),
            lambda d: d['items'][0].update(dependsOn=[d['items'][0]['id']]),
            lambda d: d['items'][0].update(status='accepted'),
            lambda d: d['items'][0].update(acceptance=[]),
            lambda d: d['items'][0].update(issueNumber=True),
            lambda d: d['items'][0].update(domainIds=['unknown']),
            lambda d: [i.update(status='in_progress') for i in d['items']],
            lambda d: [i.update(status='backlog') for i in d['items']],
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(mutation=index):
                data = copy.deepcopy(original)
                mutate(data)
                with self.assertRaises(AssertionError):
                    validate_backlog(data)

    def test_active_markers_cannot_be_missing_duplicate_or_stale(self):
        text = (ROOT / 'AGENTS.md').read_text()
        current_block(text)
        for changed in (text.replace('<!-- mvp-current:start -->', ''),
                        text + text,
                        text.replace('D96', 'D95'),
                        text.replace('full_architecture=false', 'full_architecture=true'),
                        text.replace('mvp-backlog.json', 'historical.json')):
            with self.assertRaises(AssertionError):
                current_block(changed)


if __name__ == '__main__':
    unittest.main(verbosity=2)
