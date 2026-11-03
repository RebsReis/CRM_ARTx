/* eslint-disable @typescript-eslint/no-require-imports -- CommonJS harness for evaluating transpiled TSX in a VM. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const path = require('node:path');

// Execute the actual component with a small hook/timer harness, without a browser
// or database writes. Async requests remain controllable to test response races.
function setup() {
  const values = [];
  let cursor = 0;
  let effect;
  let dependencies;
  let interval;
  let cleanup;
  let calls = 0;
  let total = 1;
  let pendingSave;
  let pendingRead;
  let deferRead = false;
  const listeners = new Map();
  const meta = { id: 1, ano: 2026, mes: 10, meta_prospeccoes: 300, meta_reunioes: 30, meta_faturamento: 20000 };
  const json = (data) => ({ ok: true, status: 200, json: async () => data });
  const hooks = {
    useState(initial) {
      const i = cursor++;
      if (!(i in values)) values[i] = typeof initial === 'function' ? initial() : initial;
      return [values[i], (next) => { values[i] = typeof next === 'function' ? next(values[i]) : next; }];
    },
    useRef(initial) { const i = cursor++; return values[i] ??= { current: initial }; },
    useEffect(fn, deps) {
      cursor++;
      if (!dependencies || deps.some((value, index) => value !== dependencies[index])) {
        dependencies = deps;
        effect = fn;
      }
    },
  };
  const events = {
    addEventListener(name, fn) { listeners.set(name, fn); },
    removeEventListener(name) { listeners.delete(name); },
  };
  const context = {
    exports: {}, console, AbortController, AbortSignal,
    window: { ...events, setInterval(fn, ms) { assert.equal(ms, 10000); interval = fn; return 1; }, clearInterval() { interval = null; }, confirm: () => true },
    document: { ...events, visibilityState: 'visible' },
    require(name) { if (name === 'react') return hooks; if (name.endsWith('.css')) return {}; return require(name); },
    fetch: async (url, options = {}) => {
      calls++;
      if (options.method === 'PUT') return new Promise((resolve) => { pendingSave = () => { Object.assign(meta, JSON.parse(options.body)); resolve(json({ ...meta })); }; });
      if (deferRead && !url.includes('dashboard')) return new Promise((resolve) => { pendingRead = () => resolve(json({ ...meta })); });
      return json(url.includes('dashboard') ? {
        prospeccoes: { prospeccoes_realizadas: total, percentual_atingido: total / 3, faltam: 300 - total },
        reunioes: { reunioes_realizadas: 0, percentual_atingido: 0, faltam: 30 },
        faturamento: { faturamento_recorrente: 0, percentual_atingido: 0, faltam: 20000 },
      } : { ...meta });
    },
  };
  const source = fs.readFileSync(path.join(__dirname, '../app/metas/Metas.tsx'), 'utf8').replace('function MetasDoPeriodo(', 'export function MetasDoPeriodo(');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  vm.runInNewContext(compiled, context);
  function render() {
    cursor = 0;
    const result = context.exports.MetasDoPeriodo({ periodo: '2026-10', aoSalvar() {} });
    if (effect) { cleanup?.(); const next = effect; effect = null; cleanup = next(); }
    return result;
  }
  render();
  return {
    values, render, listeners, context,
    get calls() { return calls; },
    tick() { interval(); },
    total(value) { total = value; },
    save() { pendingSave(); },
    defer() { deferRead = true; },
    resolveRead() { pendingRead(); },
    cleanup() { cleanup(); assert.equal(interval, null); assert.equal(listeners.size, 0); },
  };
}
async function settle() { for (let i = 0; i < 4; i++) await new Promise(setImmediate); }
function find(node, predicate) {
  if (!node || typeof node !== 'object') return undefined;
  if (Array.isArray(node)) return node.map((child) => find(child, predicate)).find(Boolean);
  if (predicate(node)) return node;
  return find(node.props?.children, predicate);
}

test('polling and focus refresh the actual indicators without overwriting a draft', async () => {
  const h = setup(); await settle();
  assert.equal(h.values[1].prospeccoes.prospeccoes_realizadas, 1);
  const input = find(h.render(), (node) => node.type === 'input' && node.props.value === '300');
  input.props.onChange({ target: { value: '999' } });
  h.total(2); h.tick(); await settle();
  assert.equal(h.values[1].prospeccoes.prospeccoes_realizadas, 2);
  assert.equal(h.values[2].meta_prospeccoes, '999');
  h.total(3); h.listeners.get('focus')(); await settle();
  assert.equal(h.values[1].prospeccoes.prospeccoes_realizadas, 3);
  assert.equal(h.values[2].meta_prospeccoes, '999');
  h.cleanup();
});

test('background refresh pauses during save and resumes afterwards', async () => {
  const h = setup(); await settle();
  const saving = find(h.render(), (node) => node.type === 'form').props.onSubmit({ preventDefault() {} });
  const calls = h.calls; h.tick(); await settle(); assert.equal(h.calls, calls);
  h.total(4); h.save(); await saving;
  assert.equal(h.values[1].prospeccoes.prospeccoes_realizadas, 4);
  h.total(5); h.tick(); await settle();
  assert.equal(h.values[1].prospeccoes.prospeccoes_realizadas, 5);
  h.cleanup();
});

test('manual reload fetches and displays the new API result', async () => {
  const h = setup(); await settle();
  const calls = h.calls;
  const button = find(h.render(), (node) => node.type === 'button' && node.props.children === 'Recarregar consulta');
  h.total(7); button.props.onClick(); h.render(); await settle();
  assert.equal(h.calls, calls + 2);
  assert.equal(h.values[1].prospeccoes.prospeccoes_realizadas, 7);
  const card = find(h.render(), (node) => node.props?.className === 'metas-value');
  assert.equal(card.props.children, '7');
  h.cleanup();
});

test('hidden tabs do not poll, requests do not overlap, and unmounted responses are ignored', async () => {
  const h = setup(); await settle(); const calls = h.calls;
  h.context.document.visibilityState = 'hidden'; h.tick(); assert.equal(h.calls, calls);
  h.context.document.visibilityState = 'visible'; h.defer(); h.tick(); const pending = h.calls;
  h.tick(); h.listeners.get('focus')(); assert.equal(h.calls, pending);
  h.cleanup(); h.resolveRead(); await settle(); assert.equal(h.calls, pending);
});
