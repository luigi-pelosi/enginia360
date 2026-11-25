import test from 'node:test';
import assert from 'node:assert/strict';
import {catalogHarness, catalogSession, findCatalog} from './catalog-harness.ts';
import {catalogRoutes, navigationPath} from '../lib/model.ts';

test('Sistema retains geography and currencies without a Catalogo tile; catalog routes remain available', () => {
  const h = catalogHarness();
  const resources = ['settings', 'countries', 'cities', 'currencies', ...catalogRoutes].map(key => ({key, fields: []}));
  const system = h.workspace({0: {...catalogSession, permissions:[...catalogSession.permissions,'countries.read','cities.read','currencies.read']}, 1: false, 5: resources, 6: 'settings-system', 7: 't'}).default();
  const text = (n: any): string => typeof n === 'string' ? n : n?.props ? [n.props.children].flat(Infinity).map(text).join(' ') : '';
  const grid = findCatalog(system, n => n.type === 'div' && n.props?.className === 'grid gap-4 sm:grid-cols-2 xl:grid-cols-3');
  assert.ok(grid);
  const tiles = [grid.props.children].flat(Infinity).filter((n: any) => n?.type === 'button').map((n: any) => text(n).trim());
  assert.deepEqual(tiles, ['Nazioni', 'Città', 'Valute', 'Unità di misura']);
  assert.deepEqual(navigationPath('catalog-categories'), ['catalog', 'catalog-categories']);
  assert.deepEqual(navigationPath('catalog-types'), ['settings', 'settings-master-data', 'settings-catalog', 'catalog-types']);
  assert.deepEqual(navigationPath('catalog-numbering'), ['settings', 'settings-master-data', 'settings-catalog', 'catalog-numbering']);
});
