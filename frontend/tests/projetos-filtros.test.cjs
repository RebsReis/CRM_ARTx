/* eslint-disable @typescript-eslint/no-require-imports -- Executa os helpers TypeScript reais no Node. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const context = { exports: {} };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/projetos.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
const { selecionarProjetos, situacaoPrazo } = context.exports;
const hoje = '2026-10-26';
const projetos = [
  { id: 1, status: 'PENDENTE', prazo: '2026-11-01' },
  { id: 2, status: 'PENDENTE', prazo: null },
  { id: 3, status: 'PENDENTE', prazo: hoje },
  { id: 4, status: 'EM_ANDAMENTO', prazo: '2026-10-20' },
  { id: 5, status: 'FINALIZADA', prazo: '2026-10-01' },
  { id: 6, status: 'CONCLUIDO', prazo: hoje },
];
const ids = (lista) => Array.from(lista, (p) => p.id);
test('vencidos e entregas de hoje aparecem primeiro sem modificar a lista original', () => {
  assert.deepEqual(ids(selecionarProjetos(projetos, hoje, '')).slice(0, 2), [4, 3]);
  assert.deepEqual(ids(projetos), [1, 2, 3, 4, 5, 6]);
});
test('filtros de prazo excluem concluidos e projetos sem prazo', () => {
  assert.deepEqual(ids(selecionarProjetos(projetos, hoje, 'urgentes')), [4, 3]);
  assert.deepEqual(ids(selecionarProjetos(projetos, hoje, 'vencidos')), [4]);
  assert.deepEqual(ids(selecionarProjetos(projetos, hoje, 'hoje')), [3]);
});
test('pendentes podem ser filtrados junto com o prazo', () => {
  const pendentes = projetos.filter((p) => p.status === 'PENDENTE');
  assert.deepEqual(ids(selecionarProjetos(pendentes, hoje, 'urgentes')), [3]);
});
test('datas com horario e virada de dia seguem a data brasileira fornecida', () => {
  assert.equal(situacaoPrazo({ status: 'PENDENTE', prazo: hoje + 'T23:59:00' }, hoje), 'hoje');
  assert.equal(situacaoPrazo(projetos[2], '2026-10-27'), 'vencido');
  assert.equal(situacaoPrazo(projetos[2], ''), 'normal');
});
