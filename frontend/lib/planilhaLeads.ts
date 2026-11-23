// Importação e exportação de leads em planilhas (.xlsx, .xls, .csv).
// A parte de validação/mapeamento é pura (testada em tests/planilha-leads.test.cjs);
// a leitura/escrita de arquivos carrega o SheetJS só quando é usada.

export type LeadPlanilha = {
  id: number;
  nome_empresa: string;
  nicho: string | null;
  telefone: string | null;
  email: string | null;
  fase: string;
  observacao: string | null;
  criado_em?: string | null;
  atualizado_em?: string | null;
};

export type CampoImportacao = "nome_empresa" | "nicho" | "telefone" | "email" | "fase" | "observacao";

export type LeadImportado = {
  linha: number;
  nome_empresa: string;
  nicho: string | null;
  telefone: string | null;
  email: string | null;
  fase: string;
  observacao: string | null;
};

export type LinhaPrevia = {
  linha: number;
  lead: LeadImportado;
  erros: string[];
  duplicado: string | null;
};

/** Mapeamento campo do sistema -> índice da coluna na planilha (-1 = não importar). */
export type Mapeamento = Record<CampoImportacao, number>;

export const ETAPAS = [
  { codigo: "PROSPECTAR", nome: "Prospectar" },
  { codigo: "FOLLOW_UP", nome: "Follow-up" },
  { codigo: "REUNIAO_MARCADA", nome: "Reunião Marcada" },
  { codigo: "REMARKETING_FUTURO", nome: "Remarketing Futuro" },
] as const;

export const CAMPOS: { chave: CampoImportacao; rotulo: string; obrigatorio: boolean; max?: number; descricao: string; sinonimos: string[] }[] = [
  { chave: "nome_empresa", rotulo: "Empresa", obrigatorio: true, max: 150, descricao: "Nome da empresa (obrigatório).",
    sinonimos: ["nome empresa", "empresa", "nome da empresa", "razao social", "nome fantasia", "cliente", "nome", "company", "lead"] },
  { chave: "nicho", rotulo: "Nicho", obrigatorio: false, max: 100, descricao: "Segmento ou ramo de atuação.",
    sinonimos: ["nicho", "segmento", "ramo", "setor", "categoria", "area de atuacao", "industry"] },
  { chave: "telefone", rotulo: "Telefone", obrigatorio: false, max: 30, descricao: "Telefone ou WhatsApp com DDD.",
    sinonimos: ["telefone", "fone", "tel", "celular", "whatsapp", "whats", "contato", "telefone celular", "phone"] },
  { chave: "email", rotulo: "E-mail", obrigatorio: false, max: 150, descricao: "E-mail de contato.",
    sinonimos: ["email", "e mail", "correio eletronico", "endereco de email", "mail"] },
  { chave: "fase", rotulo: "Etapa", obrigatorio: false, descricao: "Prospectar, Follow-up, Reunião Marcada ou Remarketing Futuro. Vazio = Prospectar.",
    sinonimos: ["fase", "etapa", "status", "estagio", "etapa comercial", "funil", "stage"] },
  { chave: "observacao", rotulo: "Observações", obrigatorio: false, descricao: "Anotações livres sobre o lead.",
    sinonimos: ["observacao", "observacoes", "obs", "notas", "anotacoes", "comentarios", "comentario", "descricao", "notes"] },
];

export const LIMITE_LINHAS = 2000;
// Só valem como nome exato da coluna; como trecho confundiriam ("Nome do contato" não é telefone).
const AMBIGUOS = new Set(["contato", "cliente", "status", "descricao", "comentario"]);
const EMAIL_VALIDO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizarTexto(valor: string) {
  return valor.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

export function apenasDigitos(valor: string | null | undefined) {
  return (valor ?? "").replace(/\D/g, "");
}

export function normalizarEmail(valor: string | null | undefined) {
  return (valor ?? "").trim().toLowerCase();
}

/** Converte o conteúdo de uma célula em texto, sem notação científica para números longos. */
export function textoCelula(valor: unknown): string {
  if (valor === null || valor === undefined) return "";
  if (typeof valor === "number") return Number.isInteger(valor) ? valor.toFixed(0) : String(valor);
  if (valor instanceof Date) return valor.toISOString().slice(0, 10);
  return String(valor).trim();
}

/** Aceita o código (FOLLOW_UP) ou o nome (Follow-up, follow up). Vazio vira PROSPECTAR; desconhecido vira null. */
export function normalizarFase(valor: string): string | null {
  const texto = normalizarTexto(valor);
  if (!texto) return "PROSPECTAR";
  const etapa = ETAPAS.find((e) => normalizarTexto(e.codigo) === texto || normalizarTexto(e.nome) === texto);
  if (etapa) return etapa.codigo;
  if (texto.startsWith("reuniao")) return "REUNIAO_MARCADA";
  if (texto.startsWith("remarketing")) return "REMARKETING_FUTURO";
  return null;
}

export function nomeEtapa(codigo: string) {
  return ETAPAS.find((e) => e.codigo === codigo)?.nome ?? codigo;
}

/** Sugere o de/para: primeiro nomes idênticos, depois cabeçalhos que contenham um sinônimo. */
export function sugerirMapeamento(cabecalhos: string[]): Mapeamento {
  const normalizados = cabecalhos.map(normalizarTexto);
  const usados = new Set<number>();
  const mapa = Object.fromEntries(CAMPOS.map((c) => [c.chave, -1])) as Mapeamento;
  const atribuir = (campo: CampoImportacao, indice: number) => {
    if (indice >= 0 && mapa[campo] < 0) { mapa[campo] = indice; usados.add(indice); }
  };
  // 1ª passada: nome idêntico (ex.: "E-mail", "nome_empresa").
  for (const campo of CAMPOS) {
    const alvos = [normalizarTexto(campo.chave), ...campo.sinonimos];
    atribuir(campo.chave, normalizados.findIndex((c, i) => !usados.has(i) && alvos.includes(c)));
  }
  // 2ª passada: cabeçalho que contém um sinônimo específico (ex.: "Telefone comercial").
  for (const campo of CAMPOS) {
    if (mapa[campo.chave] >= 0) continue;
    const trechos = campo.sinonimos.filter((s) => s.length > 4 && !AMBIGUOS.has(s));
    atribuir(campo.chave, normalizados.findIndex((c, i) => !usados.has(i) && trechos.some((s) => c.includes(s))));
  }
  return mapa;
}

/**
 * Monta a pré-visualização: aplica o mapeamento, valida cada linha e marca duplicados
 * (contra os leads já cadastrados e contra linhas válidas anteriores da própria planilha).
 * `linhas` não inclui o cabeçalho; `primeiraLinha` é o número da 1ª linha de dados no arquivo.
 */
export function montarPrevia(
  linhas: unknown[][],
  mapeamento: Mapeamento,
  existentes: Pick<LeadPlanilha, "email" | "telefone">[],
  primeiraLinha = 2,
): LinhaPrevia[] {
  const emails = new Set(existentes.map((l) => normalizarEmail(l.email)).filter(Boolean));
  const telefones = new Set(existentes.map((l) => apenasDigitos(l.telefone)).filter(Boolean));
  const emailsArquivo = new Map<string, number>();
  const telefonesArquivo = new Map<string, number>();
  const previa: LinhaPrevia[] = [];

  linhas.forEach((celulas, posicao) => {
    if (!celulas.some((c) => textoCelula(c) !== "")) return; // linha totalmente vazia
    const linha = primeiraLinha + posicao;
    const valor = (campo: CampoImportacao) => {
      const indice = mapeamento[campo];
      return indice >= 0 ? textoCelula(celulas[indice]) : "";
    };
    const erros: string[] = [];
    const nome = valor("nome_empresa").replace(/\s+/g, " ");
    const faseOriginal = valor("fase");
    const fase = normalizarFase(faseOriginal);
    const email = normalizarEmail(valor("email"));
    const telefone = valor("telefone");

    if (!nome) erros.push("Nome da empresa é obrigatório.");
    if (fase === null) erros.push(`Etapa desconhecida: "${faseOriginal}".`);
    if (email && !EMAIL_VALIDO.test(email)) erros.push(`E-mail inválido: "${email}".`);
    const lead: LeadImportado = {
      linha,
      nome_empresa: nome,
      nicho: valor("nicho") || null,
      telefone: telefone || null,
      email: email || null,
      fase: fase ?? "PROSPECTAR",
      observacao: valor("observacao") || null,
    };
    for (const campo of CAMPOS) {
      const texto = lead[campo.chave];
      if (campo.max && texto && texto.length > campo.max) erros.push(`${campo.rotulo} passa de ${campo.max} caracteres.`);
    }

    let duplicado: string | null = null;
    const digitos = apenasDigitos(telefone);
    if (email && emails.has(email)) duplicado = "E-mail já cadastrado.";
    else if (digitos && telefones.has(digitos)) duplicado = "Telefone já cadastrado.";
    else if (email && emailsArquivo.has(email)) duplicado = `E-mail repetido (linha ${emailsArquivo.get(email)}).`;
    else if (digitos && telefonesArquivo.has(digitos)) duplicado = `Telefone repetido (linha ${telefonesArquivo.get(digitos)}).`;

    if (!erros.length && !duplicado) {
      if (email) emailsArquivo.set(email, linha);
      if (digitos) telefonesArquivo.set(digitos, linha);
    }
    previa.push({ linha, lead, erros, duplicado });
  });
  return previa;
}

/** Linhas da exportação, com cabeçalhos amigáveis (reconhecidos de volta na importação). */
export function linhasExportacao(leads: LeadPlanilha[]) {
  const data = (valor?: string | null) => {
    if (!valor) return "";
    const d = new Date(valor);
    return Number.isNaN(d.getTime()) ? valor : d.toLocaleString("pt-BR");
  };
  return leads.map((lead) => ({
    ID: lead.id,
    Empresa: lead.nome_empresa,
    Nicho: lead.nicho ?? "",
    Telefone: lead.telefone ?? "",
    "E-mail": lead.email ?? "",
    Etapa: nomeEtapa(lead.fase),
    "Observações": lead.observacao ?? "",
    "Criado em": data(lead.criado_em),
    "Atualizado em": data(lead.atualizado_em),
  }));
}

// ---------- Arquivos (SheetJS carregado sob demanda) ----------

const carregarXlsx = () => import("xlsx");

export type PlanilhaLida = { cabecalhos: string[]; linhas: unknown[][]; linhaCabecalho: number };

export async function lerPlanilha(arquivo: File): Promise<PlanilhaLida> {
  const XLSX = await carregarXlsx();
  const bytes = await arquivo.arrayBuffer();
  let livro;
  if (/\.csv$/i.test(arquivo.name) || arquivo.type === "text/csv") {
    // CSV salvo pelo Excel em pt-BR costuma vir em Windows-1252; raw mantém zeros à esquerda.
    let texto: string;
    try { texto = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
    catch { texto = new TextDecoder("windows-1252").decode(bytes); }
    livro = XLSX.read(texto.replace(/^﻿/, ""), { type: "string", raw: true });
  } else {
    livro = XLSX.read(bytes, { type: "array" });
  }
  const aba = livro.Sheets[livro.SheetNames[0]];
  if (!aba) throw new Error("A planilha está vazia.");
  const matriz = XLSX.utils.sheet_to_json<unknown[]>(aba, { header: 1, defval: "", raw: true, blankrows: true });
  const inicio = matriz.findIndex((linha) => linha.some((c) => textoCelula(c) !== ""));
  if (inicio < 0) throw new Error("Não encontramos dados na planilha.");
  const cabecalhos = matriz[inicio].map(textoCelula);
  const linhas = matriz.slice(inicio + 1);
  return { cabecalhos, linhas, linhaCabecalho: inicio + 1 };
}

function dataArquivo() {
  return new Date().toISOString().slice(0, 10);
}

export async function exportarLeads(leads: LeadPlanilha[], formato: "xlsx" | "csv") {
  const XLSX = await carregarXlsx();
  const aba = XLSX.utils.json_to_sheet(linhasExportacao(leads), {
    header: ["ID", "Empresa", "Nicho", "Telefone", "E-mail", "Etapa", "Observações", "Criado em", "Atualizado em"],
  });
  const nome = `leads-artx-${dataArquivo()}`;
  if (formato === "csv") {
    // ";" + BOM para o Excel em português abrir com acentos e colunas corretas.
    const csv = "﻿" + XLSX.utils.sheet_to_csv(aba, { FS: ";" });
    baixarBlob(new Blob([csv], { type: "text/csv;charset=utf-8" }), `${nome}.csv`);
    return;
  }
  aba["!cols"] = [{ wch: 6 }, { wch: 32 }, { wch: 18 }, { wch: 18 }, { wch: 30 }, { wch: 18 }, { wch: 40 }, { wch: 19 }, { wch: 19 }];
  const livro = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(livro, aba, "Leads");
  XLSX.writeFile(livro, `${nome}.xlsx`, { compression: true });
}

export async function baixarModelo() {
  const XLSX = await carregarXlsx();
  const aba = XLSX.utils.aoa_to_sheet([CAMPOS.map((c) => c.chave)]);
  aba["!cols"] = [{ wch: 32 }, { wch: 18 }, { wch: 18 }, { wch: 30 }, { wch: 20 }, { wch: 40 }];
  const instrucoes = XLSX.utils.aoa_to_sheet([
    ["Coluna", "Obrigatória", "Limite", "Descrição"],
    ...CAMPOS.map((c) => [c.chave, c.obrigatorio ? "Sim" : "Não", c.max ? `${c.max} caracteres` : "", c.descricao]),
    [],
    ["Exemplo", "", "", "Empresa Exemplo Ltda | Varejo | (11) 99999-0000 | contato@exemplo.com.br | Prospectar | Indicação do cliente X"],
    ["Duplicidade", "", "", "Linhas com e-mail ou telefone já cadastrados são ignoradas na importação."],
  ]);
  instrucoes["!cols"] = [{ wch: 14 }, { wch: 12 }, { wch: 16 }, { wch: 90 }];
  const livro = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(livro, aba, "Leads");
  XLSX.utils.book_append_sheet(livro, instrucoes, "Instruções");
  XLSX.writeFile(livro, "modelo-importacao-leads.xlsx", { compression: true });
}

function baixarBlob(blob: Blob, nome: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = nome;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
