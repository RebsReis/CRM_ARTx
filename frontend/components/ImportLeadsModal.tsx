"use client";

import { useEffect, useMemo, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { authRequest } from "./AuthShell";
import {
  CAMPOS, LIMITE_LINHAS, baixarModelo, lerPlanilha, montarPrevia, nomeEtapa, sugerirMapeamento, textoCelula,
  type LeadPlanilha, type Mapeamento, type PlanilhaLida,
} from "../lib/planilhaLeads";

type Etapa = "arquivo" | "mapeamento" | "previa" | "resumo";
type RespostaImportacao = { importados: number; ignorados: { linha: number; motivo: string }[]; leads: LeadPlanilha[] };
type Resumo = { importados: number; comErro: { linha: number; motivo: string }[]; duplicados: { linha: number; motivo: string }[] };

const PASSOS: { id: Etapa; nome: string }[] = [
  { id: "arquivo", nome: "Arquivo" }, { id: "mapeamento", nome: "Colunas" },
  { id: "previa", nome: "Pré-visualização" }, { id: "resumo", nome: "Resumo" },
];
const EXTENSOES = /\.(xlsx|xls|csv)$/i;
const LINHAS_NA_PREVIA = 200;

export default function ImportLeadsModal({ leadsExistentes, fechar, aoImportar }: {
  leadsExistentes: LeadPlanilha[];
  fechar: () => void;
  aoImportar: (leads: LeadPlanilha[]) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [etapa, setEtapa] = useState<Etapa>("arquivo");
  const [arquivo, setArquivo] = useState<string>("");
  const [planilha, setPlanilha] = useState<PlanilhaLida | null>(null);
  const [mapeamento, setMapeamento] = useState<Mapeamento | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [arrastando, setArrastando] = useState(false);
  const [erro, setErro] = useState("");
  const [resumo, setResumo] = useState<Resumo | null>(null);

  useEffect(() => { const modal = dialog.current; modal?.showModal(); return () => modal?.close(); }, []);

  const previa = useMemo(() => planilha && mapeamento
    ? montarPrevia(planilha.linhas, mapeamento, leadsExistentes, planilha.linhaCabecalho + 1)
    : [], [planilha, mapeamento, leadsExistentes]);
  const validas = previa.filter((l) => !l.erros.length && !l.duplicado);
  const comErro = previa.filter((l) => l.erros.length);
  const duplicadas = previa.filter((l) => !l.erros.length && l.duplicado);

  async function carregarArquivo(file: File | undefined) {
    if (!file || ocupado) return;
    setErro("");
    if (!EXTENSOES.test(file.name)) { setErro("Envie um arquivo .xlsx, .xls ou .csv."); return; }
    if (file.size > 10 * 1024 * 1024) { setErro("O arquivo passa de 10 MB."); return; }
    setOcupado(true);
    try {
      const lida = await lerPlanilha(file);
      if (!lida.linhas.some((linha) => linha.some((c) => textoCelula(c) !== ""))) throw new Error("A planilha só tem o cabeçalho, sem linhas de dados.");
      setArquivo(file.name);
      setPlanilha(lida);
      setMapeamento(sugerirMapeamento(lida.cabecalhos));
      setEtapa("mapeamento");
    } catch (e) {
      setErro(e instanceof Error && e.message ? e.message : "Não foi possível ler o arquivo.");
    } finally { setOcupado(false); }
  }

  function aoSoltar(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault(); setArrastando(false);
    void carregarArquivo(event.dataTransfer.files[0]);
  }

  async function modelo() {
    try { await baixarModelo(); } catch { setErro("Não foi possível gerar a planilha modelo."); }
  }

  async function importar() {
    if (!validas.length || ocupado) return;
    setOcupado(true); setErro("");
    try {
      const resposta = await authRequest<RespostaImportacao>("/leads/importar", {
        method: "POST", body: JSON.stringify({ leads: validas.map((l) => l.lead) }),
      });
      aoImportar(resposta.leads);
      setResumo({
        importados: resposta.importados,
        comErro: comErro.map((l) => ({ linha: l.linha, motivo: l.erros.join(" ") })),
        duplicados: [...duplicadas.map((l) => ({ linha: l.linha, motivo: l.duplicado ?? "" })), ...resposta.ignorados]
          .sort((a, b) => a.linha - b.linha),
      });
      setEtapa("resumo");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Não foi possível importar os leads.");
    } finally { setOcupado(false); }
  }

  const exemplo = (indice: number) => {
    if (!planilha || indice < 0) return "";
    const linha = planilha.linhas.find((l) => textoCelula(l[indice]) !== "");
    return linha ? textoCelula(linha[indice]) : "";
  };
  const indicePasso = PASSOS.findIndex((p) => p.id === etapa);
  const naoImportadas = resumo ? [
    ...resumo.duplicados.map((i) => ({ ...i, tipo: "Duplicado", classe: "is-warning" })),
    ...resumo.comErro.map((i) => ({ ...i, tipo: "Erro", classe: "is-error" })),
  ].sort((a, b) => a.linha - b.linha) : [];

  return <dialog ref={dialog} className="config-modal leads-import-modal" aria-labelledby="import-leads-title"
    onCancel={(event) => { event.preventDefault(); if (!ocupado) fechar(); }}>
    <div className="config-section-title">
      <h2 id="import-leads-title">Importar leads</h2>
      <button type="button" aria-label="Fechar importação" disabled={ocupado} onClick={fechar}>×</button>
    </div>
    <ol className="leads-import-steps" aria-label="Etapas da importação">
      {PASSOS.map((passo, i) => <li key={passo.id} aria-current={passo.id === etapa ? "step" : undefined}
        className={i < indicePasso ? "is-done" : passo.id === etapa ? "is-current" : ""}><span>{i + 1}</span>{passo.nome}</li>)}
    </ol>

    {etapa === "arquivo" && <>
      <p className="config-muted">Envie uma planilha .xlsx, .xls ou .csv. Na próxima etapa você indica qual coluna corresponde a cada campo do CRM.</p>
      <label className={`leads-dropzone${arrastando ? " is-dragging" : ""}`} onDragOver={(e) => { e.preventDefault(); setArrastando(true); }}
        onDragLeave={() => setArrastando(false)} onDrop={aoSoltar}>
        <svg aria-hidden="true" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 15V3m0 0-4 4m4-4 4 4"/><path d="M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/></svg>
        <strong>{ocupado ? "Lendo arquivo..." : "Clique para escolher ou arraste o arquivo aqui"}</strong>
        <small>.xlsx, .xls ou .csv &middot; até {LIMITE_LINHAS.toLocaleString("pt-BR")} leads por arquivo</small>
        <input type="file" accept=".xlsx,.xls,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,text/csv"
          disabled={ocupado} onChange={(e: ChangeEvent<HTMLInputElement>) => { void carregarArquivo(e.target.files?.[0]); e.target.value = ""; }}/>
      </label>
      <div className="leads-import-template">
        <div><strong>Não tem uma planilha pronta?</strong><p className="config-muted">Baixe o modelo com as colunas exatas que o CRM espera.</p></div>
        <button type="button" className="config-secondary" onClick={() => void modelo()}>Baixar planilha modelo</button>
      </div>
    </>}

    {etapa === "mapeamento" && planilha && mapeamento && <>
      <p className="config-muted">Arquivo <strong>{arquivo}</strong>. Confira de qual coluna da sua planilha vem cada campo. Sugerimos as correspondências pelo nome das colunas.</p>
      <div className="leads-map-grid">
        <span className="leads-map-head">Campo do CRM</span><span className="leads-map-head">Coluna da planilha</span><span className="leads-map-head">Exemplo</span>
        {CAMPOS.map((campo) => <div key={campo.chave} className="leads-map-row">
          <span id={`map-${campo.chave}`}>{campo.rotulo}{campo.obrigatorio && <b aria-label="obrigatório"> *</b>}</span>
          <select aria-labelledby={`map-${campo.chave}`} value={mapeamento[campo.chave]}
            onChange={(e) => setMapeamento({ ...mapeamento, [campo.chave]: Number(e.target.value) })}>
            <option value={-1}>— Não importar —</option>
            {planilha.cabecalhos.map((cabecalho, i) => <option key={i} value={i}>{cabecalho || `Coluna ${i + 1} (sem título)`}</option>)}
          </select>
          <span className="leads-map-sample" title={exemplo(mapeamento[campo.chave])}>{exemplo(mapeamento[campo.chave]) || "—"}</span>
        </div>)}
      </div>
      {mapeamento.nome_empresa < 0 && <p className="config-message config-error" role="alert">Escolha a coluna com o nome da empresa para continuar.</p>}
      <div className="config-actions">
        <button type="button" className="config-secondary" onClick={() => { setEtapa("arquivo"); setPlanilha(null); setMapeamento(null); }}>Trocar arquivo</button>
        <button type="button" className="leads-new" disabled={mapeamento.nome_empresa < 0} onClick={() => setEtapa("previa")}>Pré-visualizar</button>
      </div>
    </>}

    {etapa === "previa" && <>
      <div className="leads-import-stats" role="status">
        <span className="is-ok"><strong>{validas.length}</strong> prontos para importar</span>
        <span className="is-warning"><strong>{duplicadas.length}</strong> duplicados</span>
        <span className="is-error"><strong>{comErro.length}</strong> com erro</span>
      </div>
      <p className="config-muted">Apenas as linhas válidas serão salvas. Duplicados (e-mail ou telefone já existentes) e linhas com erro serão ignorados.</p>
      <div className="leads-preview-wrap">
        <table className="leads-preview">
          <thead><tr><th>Linha</th><th>Situação</th>{CAMPOS.filter((c) => mapeamento && mapeamento[c.chave] >= 0).map((c) => <th key={c.chave}>{c.rotulo}</th>)}</tr></thead>
          <tbody>{previa.slice(0, LINHAS_NA_PREVIA).map((l) => {
            const situacao = l.erros.length ? "is-error" : l.duplicado ? "is-warning" : "is-ok";
            return <tr key={l.linha} className={situacao}>
              <td>{l.linha}</td>
              <td><span className={`leads-badge ${situacao}`}>{l.erros.length ? "Erro" : l.duplicado ? "Duplicado" : "OK"}</span>
                {(l.erros.length > 0 || l.duplicado) && <small>{l.erros.join(" ") || l.duplicado}</small>}</td>
              {CAMPOS.filter((c) => mapeamento && mapeamento[c.chave] >= 0).map((c) =>
                <td key={c.chave}>{c.chave === "fase" ? nomeEtapa(l.lead.fase) : l.lead[c.chave] ?? ""}</td>)}
            </tr>;
          })}</tbody>
        </table>
      </div>
      {previa.length > LINHAS_NA_PREVIA && <p className="config-muted">Mostrando as primeiras {LINHAS_NA_PREVIA} de {previa.length} linhas.</p>}
      {validas.length > LIMITE_LINHAS && <p className="config-message config-error" role="alert">O arquivo tem {validas.length} leads válidos. Divida-o em arquivos de até {LIMITE_LINHAS.toLocaleString("pt-BR")} leads.</p>}
      {erro && <p className="config-message config-error" role="alert">{erro}</p>}
      <div className="config-actions">
        <button type="button" className="config-secondary" disabled={ocupado} onClick={() => setEtapa("mapeamento")}>Voltar</button>
        <button type="button" className="leads-new" disabled={ocupado || !validas.length || validas.length > LIMITE_LINHAS} onClick={() => void importar()}>
          {ocupado ? "Importando..." : `Importar ${validas.length} ${validas.length === 1 ? "lead" : "leads"}`}
        </button>
      </div>
    </>}

    {etapa === "resumo" && resumo && <>
      <div className="leads-import-stats" role="status">
        <span className="is-ok"><strong>{resumo.importados}</strong> {resumo.importados === 1 ? "lead importado" : "leads importados"}</span>
        <span className="is-warning"><strong>{resumo.duplicados.length}</strong> ignorados por duplicidade</span>
        <span className="is-error"><strong>{resumo.comErro.length}</strong> linhas com erro</span>
      </div>
      {resumo.importados > 0 && <p className="config-message">Os leads importados já aparecem no funil.</p>}
      {naoImportadas.length > 0 && <ul className="leads-import-issues" aria-label="Linhas não importadas">
        {naoImportadas.map((i) => <li key={`${i.tipo}-${i.linha}`}><span className={`leads-badge ${i.classe}`}>{i.tipo}</span> Linha {i.linha}: {i.motivo}</li>)}
      </ul>}
      <div className="config-actions"><button type="button" className="leads-new" onClick={fechar}>Concluir</button></div>
    </>}

    {erro && etapa !== "previa" && <p className="config-message config-error" role="alert">{erro}</p>}
  </dialog>;
}
