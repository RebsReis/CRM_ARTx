/* eslint-disable @typescript-eslint/no-require-imports -- Executa os helpers TypeScript reais no Node. */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('typescript');
const context = { exports: {}, require };
vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/planilhaLeads.ts'), 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText, context);
const { sugerirMapeamento, montarPrevia, normalizarFase, textoCelula, linhasExportacao } = context.exports;
const plain = (valor) => JSON.parse(JSON.stringify(valor));

test('mapeamento automatico reconhece nomes diferentes de coluna', () => {
  const mapa = sugerirMapeamento(['Razão Social', 'Nome do contato', 'WhatsApp', 'E-mail', 'Segmento', 'Status', 'Obs.']);
  assert.deepEqual(plain(mapa), { nome_empresa: 0, nicho: 4, telefone: 2, email: 3, fase: 5, observacao: 6 });
});

test('mapeamento usa as colunas exatas da planilha modelo', () => {
  const mapa = sugerirMapeamento(['nome_empresa', 'nicho', 'telefone', 'email', 'fase', 'observacao']);
  assert.deepEqual(plain(mapa), { nome_empresa: 0, nicho: 1, telefone: 2, email: 3, fase: 4, observacao: 5 });
});

test('trechos ambiguos nao viram telefone e colunas sem par ficam fora', () => {
  const mapa = sugerirMapeamento(['Empresa', 'Nome do contato', 'Telefone comercial']);
  assert.equal(mapa.nome_empresa, 0);
  assert.equal(mapa.telefone, 2);
  assert.equal(mapa.email, -1);
});

test('etapa aceita codigo, nome com acento ou vazio', () => {
  assert.equal(normalizarFase(''), 'PROSPECTAR');
  assert.equal(normalizarFase('follow up'), 'FOLLOW_UP');
  assert.equal(normalizarFase('Reunião marcada'), 'REUNIAO_MARCADA');
  assert.equal(normalizarFase('REMARKETING_FUTURO'), 'REMARKETING_FUTURO');
  assert.equal(normalizarFase('Ganhou'), null);
});

test('numeros longos de telefone nao viram notacao cientifica', () => {
  assert.equal(textoCelula(5511999998888), '5511999998888');
  assert.equal(textoCelula('  texto '), 'texto');
});

test('previa valida obrigatorios e marca duplicados do banco e do proprio arquivo', () => {
  const mapa = { nome_empresa: 0, telefone: 1, email: 2, fase: 3, nicho: -1, observacao: -1 };
  const linhas = [
    ['Acme', '(11) 99999-0000', 'CONTATO@acme.com', 'Follow-up'],
    ['', '11 3333-0000', '', ''],
    ['Beta', '', 'nao-e-email', ''],
    ['Gama', '+55 11 98888-7777', '', ''],
    ['', '', '', ''],
    ['Delta', '', 'contato@acme.com', ''],
    ['Épsilon', '11999990000', '', 'Fechado'],
    ['Zeta', '', 'zeta@ex.com', ''],
  ];
  const existentes = [{ email: null, telefone: '5511988887777' }];
  const previa = montarPrevia(linhas, mapa, existentes, 2);
  const resumo = previa.map((l) => [l.linha, l.erros.length > 0, l.duplicado]);
  assert.deepEqual(plain(resumo), [
    [2, false, null],
    [3, true, null],
    [4, true, null],
    [5, false, 'Telefone já cadastrado.'],
    [7, false, 'E-mail repetido (linha 2).'],
    [8, true, 'Telefone repetido (linha 2).'],
    [9, false, null],
  ]);
  assert.equal(previa[0].lead.email, 'contato@acme.com');
  assert.equal(previa[0].lead.fase, 'FOLLOW_UP');
  assert.equal(previa[0].lead.linha, 2);
});

test('exportacao usa rotulos amigaveis e nome da etapa', () => {
  const [linha] = linhasExportacao([{ id: 7, nome_empresa: 'Acme', nicho: null, telefone: '11', email: null, fase: 'REUNIAO_MARCADA', observacao: null }]);
  assert.equal(linha.Empresa, 'Acme');
  assert.equal(linha.Etapa, 'Reunião Marcada');
  assert.equal(linha.Nicho, '');
  const mapa = sugerirMapeamento(Object.keys(linha));
  assert.equal(mapa.nome_empresa, 1);
  assert.equal(mapa.fase, 5);
  assert.equal(mapa.observacao, 6);
});
