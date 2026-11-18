import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const read = (path: string) => readFileSync(new URL('../' + path, import.meta.url));

test('approved logo is available in the Next public directory', () => {
  const png = read('public/enginia360-logo.png');
  assert.equal(png.subarray(0, 8).toString('hex'), '89504e470d0a1a0a');
  assert.equal(png.readUInt32BE(16), 1487);
  assert.equal(png.readUInt32BE(20), 244);
  assert.equal(png[25], 6);
});

test('standalone runtime includes public assets', () => {
  assert.match(read('Dockerfile').toString(), /COPY --from=build --chown=node:node \/app\/public \.\/public/);
});

test('shared brand renders the supplied logo with an accessible name', () => {
  const source = read('components/workspace.tsx').toString();
  assert.match(source, /return <img src="\/enginia360-logo\.png" alt="Enginia360"/);
});

test('sidebar logo fills the available panel width without changing login sizing', () => {
  const source = read('components/workspace.tsx').toString();
  assert.match(source, /<SidebarHeader[^>]*><Brand className="h-auto w-full object-contain"/);
  assert.match(source, /className = "h-7 w-auto max-w-full object-contain object-left"/);
});
