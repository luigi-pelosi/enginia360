import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import ts from 'typescript';

const read = (path: string) => readFileSync(new URL('../' + path, import.meta.url), 'utf8');
function driver(desktop = true) {
  const effects: Array<() => void> = [];
  const listeners: Record<string, () => void> = {};
  const window = {innerWidth: 1440, innerHeight: 1000, matchMedia: () => ({matches: desktop, addEventListener() {}, removeEventListener() {}}), addEventListener: (name: string, fn: () => void) => {listeners[name] = fn;}, removeEventListener() {}};
  const module = {exports: {} as any};
  runInNewContext(ts.transpileModule(read('components/ui/use-dialog-window.ts'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText, {module, exports: module.exports, window, require: () => ({useRef: (current: any) => ({current}), useEffect: (fn: () => void) => effects.push(fn)})});
  const handlers = module.exports.useDialogWindow();
  effects.forEach(fn => fn());
  const styles: Record<string, string> = {};
  let captured = false;
  const node = {dataset: {} as Record<string, string>, style: {setProperty: (k: string, v: string) => {styles[k] = v;}, removeProperty: (k: string) => {delete styles[k];}}, getBoundingClientRect: () => ({left: 384, top: 100, width: 672, height: 800}), setPointerCapture() {captured = true;}, hasPointerCapture: () => captured, releasePointerCapture() {captured = false;}};
  const event = (kind = 'header', x = 400, y = 120) => ({button: 0, pointerId: 1, clientX: x, clientY: y, currentTarget: node, target: {closest: (selector: string) => selector.includes("dialog-content") ? node : selector === '[data-dialog-resize]' ? (kind === 'resize' ? {} : null) : selector.includes('dialog-header') ? (kind === 'header' || kind === 'button' || kind === 'tab' || (kind === 'title' && selector.includes('dialog-title')) ? {} : null) : (kind === 'button' || (kind === 'tab' && selector.includes("[role='tab']")) ? {} : null)}, preventDefault() {}});
  return {handlers, styles, node, event, listeners};
}

test('both modal primitives share desktop window behavior without wrapping content', () => {
  for (const file of ['dialog', 'alert-dialog']) {
    const source = read(`components/ui/${file}.tsx`);
    assert.match(source, /useDialogWindow\(\)/);
    assert.match(source, /data-dialog-resize/);
  }
});
test('desktop header drag preserves size and clamps inside viewport', () => {
  const d = driver();
  d.handlers.onPointerDown(d.event());
  d.handlers.onPointerMove(d.event('header', 5000, 5000));
  assert.equal(d.styles['--dialog-left'], '752px');
  assert.equal(d.styles['--dialog-top'], '184px');
  assert.equal(d.styles['--dialog-width'], '672px');
  assert.equal(d.styles['--dialog-height'], '800px');
  d.handlers.onPointerUp(d.event());
  d.handlers.onPointerMove(d.event('header', 500, 200));
  assert.equal(d.styles['--dialog-left'], '752px');
});
test('resize supports enlargement and shrinkage with minimum size', () => {
  const d = driver();
  d.handlers.onPointerDown(d.event('resize'));
  d.handlers.onPointerMove(d.event('resize', 500, 220));
  assert.equal(d.styles['--dialog-width'], '772px');
  assert.equal(d.styles['--dialog-height'], '900px');
  d.handlers.onPointerMove(d.event('resize', -5000, -5000));
  assert.equal(d.styles['--dialog-width'], '384px');
  assert.equal(d.styles['--dialog-height'], '320px');
});
test('fields and header buttons do not initiate gestures', () => {
  for (const [desktop, kind] of [[true, 'field'], [true, 'button']] as const) {
    const d = driver(desktop);
    d.handlers.onPointerDown(d.event(kind));
    d.handlers.onPointerMove(d.event(kind, 700, 500));
    assert.deepEqual(d.styles, {});
  }
});
test('pointer cancel and viewport changes terminate gestures and restore responsive sizing', () => {
  const d = driver();
  d.handlers.onPointerDown(d.event());
  d.handlers.onPointerMove(d.event('header', 450, 150));
  d.handlers.onPointerCancel(d.event());
  d.handlers.onPointerMove(d.event('header', 500, 200));
  assert.equal(d.styles['--dialog-left'], '434px');
  d.listeners.resize();
  assert.deepEqual(d.styles, {});
  assert.deepEqual(d.node.dataset, {});
});

test('bare title and touch-sized viewport support drag and resize', () => {
  for (const kind of ['title', 'resize']) {
    const d = driver(false);
    d.handlers.onPointerDown(d.event(kind));
    d.handlers.onPointerMove(d.event(kind, 500, 220));
    assert.notEqual(d.styles['--dialog-left'], undefined, kind);
  }
});

test('a tab within a draggable header keeps its own interaction', () => {
  const d = driver();
  d.handlers.onPointerDown(d.event('tab'));
  d.handlers.onPointerMove(d.event('tab', 700, 500));
  assert.deepEqual(d.styles, {});
});
