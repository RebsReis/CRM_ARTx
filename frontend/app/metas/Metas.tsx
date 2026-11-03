"use client";

import { Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import "../leads/leads.css";
import "./metas.css";

type Meta = {
  id: number;
  ano: number;
  mes: number;
  meta_prospeccoes: number;
  meta_reunioes: number;
  meta_faturamento: number;
};
type Progresso = { faltam: number | null; percentual_atingido: number | null; erro?: string };
type Indicadores = {
  prospeccoes: Progresso & { meta_prospeccoes: number | null; prospeccoes_realizadas: number | null };
  reunioes: Progresso & { meta_reunioes: number | null; reunioes_realizadas: number | null };
  faturamento: Progresso & { meta_faturamento: number | null; faturamento_recorrente: number | null };
};
type Formulario = { meta_prospeccoes: string; meta_reunioes: string; meta_faturamento: string };
const vazio: Formulario = { meta_prospeccoes: "", meta_reunioes: "", meta_faturamento: "" };
const campos = [
  { campo: "meta_prospeccoes", titulo: "Prospecções", step: "1" },
  { campo: "meta_reunioes", titulo: "Reuniões agendadas", step: "1" },
  { campo: "meta_faturamento", titulo: "Faturamento recorrente (R$)", step: "0.01" },
] as const;
const numero = (valor: number) => valor.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
const moeda = (valor: number) => valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const paraFormulario = (meta: Meta): Formulario => ({
  meta_prospeccoes: String(meta.meta_prospeccoes),
  meta_reunioes: String(meta.meta_reunioes),
  meta_faturamento: String(meta.meta_faturamento),
});
const periodoAtual = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit" }).format(new Date()).slice(0, 7);

async function detalheErro(resposta: Response) {
  try {
    const dados = await resposta.json();
    if (typeof dados.detail === "string") return dados.detail;
    if (Array.isArray(dados.detail)) return "Confira os valores: as metas devem ser não negativas; prospecções e reuniões devem ser inteiras.";
  } catch { /* Respostas sem JSON usam a mensagem padrão. */ }
  return `Não foi possível concluir a solicitação (HTTP ${resposta.status}).`;
}

function MetasDoPeriodo({ periodo, aoSalvar }: { periodo: string; aoSalvar: (salvando: boolean) => void }) {
  const [ano, mes] = periodo.split("-").map(Number);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [indicadores, setIndicadores] = useState<Indicadores | null>(null);
  const [formulario, setFormulario] = useState<Formulario>(vazio);
  const [carregando, setCarregando] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [erroSalvar, setErroSalvar] = useState("");
  const [erroIndicadores, setErroIndicadores] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [revisao, setRevisao] = useState(0);
  const consulta = `ano=${ano}&mes=${mes}`;
  const formularioAlterado = useRef(false);
  const gravacaoEmCurso = useRef(false);
  const requisicaoAtual = useRef<AbortController | null>(null);

  useEffect(() => {
    let encerrado = false;
    let emCurso = false;
    async function carregar() {
      if (encerrado || emCurso || gravacaoEmCurso.current) return;
      emCurso = true;
      const controller = new AbortController();
      requisicaoAtual.current = controller;
      const signal = AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]);
      try {
        const resposta = await fetch(`/api/crm/metas?${consulta}`, { cache: "no-store", signal });
        if (controller.signal.aborted || encerrado) return;
        if (resposta.status === 404) {
          setMeta(null); setErro(""); setErroIndicadores("");
          if (!formularioAlterado.current) setFormulario(vazio);
          const consultas = await Promise.allSettled([
            fetch(`/api/crm/leads/prospeccoes/mensal?${consulta}`, { cache: "no-store", signal }),
            fetch(`/api/crm/reunioes/indicadores/mensal?${consulta}`, { cache: "no-store", signal }),
            fetch(`/api/crm/clientes/faturamento/mensal?${consulta}`, { cache: "no-store", signal }),
          ]);
          const ler = async (resultado: PromiseSettledResult<Response>) => {
            if (resultado.status === "rejected") throw resultado.reason;
            if (!resultado.value.ok) throw new Error(await detalheErro(resultado.value));
            return resultado.value.json();
          };
          const [prospeccoes, reunioes, faturamento] = await Promise.all(
            consultas.map((resultado) => ler(resultado).catch((error) => ({ erro: error instanceof Error ? error.message : "Não foi possível consultar este indicador." })))
          );
          if (controller.signal.aborted || encerrado) return;
          setIndicadores({
            prospeccoes: { meta_prospeccoes: null, prospeccoes_realizadas: typeof prospeccoes.prospeccoes_realizadas === "number" ? prospeccoes.prospeccoes_realizadas : null, faltam: null, percentual_atingido: null, erro: prospeccoes.erro },
            reunioes: { meta_reunioes: null, reunioes_realizadas: typeof reunioes.reunioes_agendadas === "number" ? reunioes.reunioes_agendadas : null, faltam: null, percentual_atingido: null, erro: reunioes.erro },
            faturamento: { meta_faturamento: null, faturamento_recorrente: typeof faturamento.faturamento_recorrente === "number" ? faturamento.faturamento_recorrente : null, faltam: null, percentual_atingido: null, erro: faturamento.erro },
          });
          return;
        }
        if (!resposta.ok) throw new Error(await detalheErro(resposta));
        const cadastro: Meta = await resposta.json();
        if (controller.signal.aborted || encerrado) return;
        setMeta(cadastro); setErro("");
        if (!formularioAlterado.current) setFormulario(paraFormulario(cadastro));
        try {
          const painel = await fetch(`/api/crm/metas/dashboard?${consulta}`, { cache: "no-store", signal });
          if (!painel.ok) throw new Error(await detalheErro(painel));
          const dados: Indicadores = await painel.json();
          if (!controller.signal.aborted && !encerrado) {
            setIndicadores(dados); setErroIndicadores("");
          }
        } catch {
          if (!controller.signal.aborted && !encerrado) setErroIndicadores("Nao foi possivel atualizar os resultados. Nova tentativa automatica em instantes.");
        }
      } catch (error) {
        if (!controller.signal.aborted && !encerrado) setErro(error instanceof Error ? error.message : "Nao foi possivel consultar as metas.");
      } finally {
        emCurso = false;
        if (!controller.signal.aborted && !encerrado) setCarregando(false);
        if (requisicaoAtual.current === controller) requisicaoAtual.current = null;
      }
    }
    const aoVoltar = () => { if (document.visibilityState === "visible") void carregar(); };
    void carregar();
    const intervalo = window.setInterval(aoVoltar, 10000);
    window.addEventListener("focus", aoVoltar);
    window.addEventListener("online", aoVoltar);
    document.addEventListener("visibilitychange", aoVoltar);
    return () => {
      encerrado = true;
      window.clearInterval(intervalo);
      window.removeEventListener("focus", aoVoltar);
      window.removeEventListener("online", aoVoltar);
      document.removeEventListener("visibilitychange", aoVoltar);
      requisicaoAtual.current?.abort();
    };
  }, [consulta, revisao]);

  function recarregar() {
    if (formularioAlterado.current && !window.confirm("Recarregar e descartar as alteracoes ainda nao salvas?")) return;
    formularioAlterado.current = false;
    setCarregando(true); setErro(""); setErroIndicadores(""); setSucesso(""); setIndicadores(null); setRevisao((valor) => valor + 1);
  }

  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (gravacaoEmCurso.current || salvando || carregando || erro) return;
    const valores = {
      meta_prospeccoes: Number(formulario.meta_prospeccoes),
      meta_reunioes: Number(formulario.meta_reunioes),
      meta_faturamento: Number(formulario.meta_faturamento),
    };
    if (Object.values(formulario).some((valor) => !valor.trim()) || Object.values(valores).some((valor) => !Number.isFinite(valor) || valor < 0) || !Number.isInteger(valores.meta_prospeccoes) || !Number.isInteger(valores.meta_reunioes)) {
      setSucesso(""); setErroSalvar("Informe metas válidas e não negativas. Prospecções e reuniões devem ser inteiras."); return;
    }
    gravacaoEmCurso.current = true;
    requisicaoAtual.current?.abort();
    setSalvando(true); aoSalvar(true); setSucesso(""); setErroSalvar("");
    try {
      const resposta = await fetch(meta ? `/api/crm/metas/${meta.id}` : "/api/crm/metas", {
        method: meta ? "PUT" : "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ano, mes, ...valores }), signal: AbortSignal.timeout(15000),
      });
      if (!resposta.ok) throw new Error(await detalheErro(resposta));
      const atualizada: Meta = await resposta.json();
      formularioAlterado.current = false;
      setMeta(atualizada); setFormulario(paraFormulario(atualizada)); setSucesso("Metas salvas com sucesso."); setIndicadores(null); setErroIndicadores("");
      try {
        const respostaIndicadores = await fetch(`/api/crm/metas/dashboard?${consulta}`, { cache: "no-store", signal: AbortSignal.timeout(15000) });
        if (!respostaIndicadores.ok) throw new Error();
        setIndicadores(await respostaIndicadores.json());
      } catch { setErroIndicadores("As metas foram salvas, mas não foi possível atualizar os resultados. Recarregue a consulta."); }
    } catch (error) {
      setErroSalvar(error instanceof Error ? error.message : "Não foi possível salvar as metas. Consulte o mês antes de tentar novamente.");
    } finally { gravacaoEmCurso.current = false; setSalvando(false); aoSalvar(false); }
  }
  const cards = [
    { titulo: "Prospecções", meta: meta ? numero(meta.meta_prospeccoes) : "Meta não definida", realizado: indicadores?.prospeccoes.erro ? "Erro" : indicadores?.prospeccoes.prospeccoes_realizadas !== null && indicadores?.prospeccoes.prospeccoes_realizadas !== undefined ? numero(indicadores.prospeccoes.prospeccoes_realizadas) : "Resultado indisponível", progresso: indicadores?.prospeccoes.percentual_atingido ?? undefined, falta: indicadores?.prospeccoes.faltam !== null && indicadores?.prospeccoes.faltam !== undefined ? `${numero(indicadores.prospeccoes.faltam)} prospecções` : null, erro: indicadores?.prospeccoes.erro },
    { titulo: "Reuniões agendadas", meta: meta ? numero(meta.meta_reunioes) : "Meta não definida", realizado: indicadores?.reunioes.erro ? "Erro" : indicadores?.reunioes.reunioes_realizadas !== null && indicadores?.reunioes.reunioes_realizadas !== undefined ? numero(indicadores.reunioes.reunioes_realizadas) : "Resultado indisponível", progresso: indicadores?.reunioes.percentual_atingido ?? undefined, falta: indicadores?.reunioes.faltam !== null && indicadores?.reunioes.faltam !== undefined ? `${numero(indicadores.reunioes.faltam)} reuniões` : null, erro: indicadores?.reunioes.erro },
    { titulo: "Faturamento recorrente", meta: meta ? moeda(meta.meta_faturamento) : "Meta não definida", realizado: indicadores?.faturamento.erro ? "Erro" : indicadores?.faturamento.faturamento_recorrente !== null && indicadores?.faturamento.faturamento_recorrente !== undefined ? moeda(indicadores.faturamento.faturamento_recorrente) : "Resultado indisponível", progresso: indicadores?.faturamento.percentual_atingido ?? undefined, falta: indicadores?.faturamento.faltam !== null && indicadores?.faturamento.faltam !== undefined ? moeda(indicadores.faturamento.faltam) : null, erro: indicadores?.faturamento.erro },
  ];

  return <div aria-busy={carregando || salvando}>
    {carregando && <p className="metas-notice" role="status">Carregando metas e resultados...</p>}
    {erro && <p className="metas-notice metas-error" role="alert">{erro}</p>}
    {!carregando && !erro && !meta && <p className="metas-notice">Nenhuma meta cadastrada para este mês. Defina as três metas no formulário abaixo.</p>}
    {erroIndicadores && <p className="metas-notice metas-error" role="alert">{erroIndicadores}</p>}
    <div className="metas-cards">{cards.map((card) => <article className="metas-card" key={card.titulo}>
      <h2>{card.titulo}</h2><span className="metas-label">Realizado</span><p className="metas-value">{card.realizado}</p><p className="metas-defined">Meta definida: <strong>{card.meta}</strong></p>
      <p className="metas-percent">{card.erro ?? (card.progresso !== undefined && card.progresso !== null ? `${numero(card.progresso)}% atingido` : meta ? "Resultado indisponível" : "Meta não definida")}</p>
      <div className="metas-progress" role="progressbar" aria-label={`Progresso de ${card.titulo}`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={card.progresso === undefined ? undefined : Math.min(100, Math.max(0, card.progresso))}><div style={{ width: `${Math.min(100, Math.max(0, card.progresso ?? 0))}%` }}/></div>
      <p className="metas-caption">{card.falta === null ? "Aguardando resultados do período" : `Faltam ${card.falta}`}</p>
    </article>)}</div>
    <p className="metas-caption">Resultados do mês selecionado: uma prospecção conta quando o lead sai de Prospectar pela primeira vez (leads ainda em Prospectar não contam); reuniões são as agendadas no mês, sem as canceladas; faturamento é o valor recorrente dos contratos ativos no mês.</p>
    <section className="metas-form-section"><div className="metas-section-heading"><div><h2>{meta ? "Editar metas mensais" : "Cadastrar metas mensais"}</h2><p>Defina os objetivos comerciais do período selecionado.</p></div><button type="button" className="metas-secondary" onClick={() => { setErroSalvar(""); recarregar(); }} disabled={carregando || salvando}>Recarregar consulta</button></div>
      <form onSubmit={salvar}>
        <fieldset disabled={carregando || salvando || !!erro}><legend className="sr-only">Metas do mês</legend><div className="metas-fields">{campos.map(({ campo, titulo, step }) => <label key={campo}>{titulo}<input type="number" required min="0" step={step} inputMode={campo === "meta_faturamento" ? "decimal" : "numeric"} value={formulario[campo]} onChange={(event) => { formularioAlterado.current = true; setFormulario((anterior) => ({ ...anterior, [campo]: event.target.value })); setErroSalvar(""); setSucesso(""); }}/></label>)}</div></fieldset>
        <p className="metas-caption">Informe valores a partir de zero. Prospecções e reuniões devem ser números inteiros.</p>
        {erroSalvar && <p className="metas-notice metas-error" role="alert">{erroSalvar} Use “Recarregar consulta” para conferir o cadastro atual.</p>}
        {sucesso && <p className="metas-notice metas-success" role="status">{sucesso}</p>}
        <div className="metas-form-actions"><button type="button" className="metas-secondary" disabled={carregando || salvando || !!erro} onClick={() => { formularioAlterado.current = false; setFormulario(meta ? paraFormulario(meta) : vazio); setSucesso(""); setErroSalvar(""); }}>Restaurar campos</button><button className="leads-new" disabled={carregando || salvando || !!erro} type="submit">{salvando ? "Salvando..." : meta ? "Salvar alterações" : "Cadastrar metas"}</button></div>
      </form>
    </section>
  </div>;
}

function MetasContent() {
  const [periodo, setPeriodo] = useState(periodoAtual);
  const [salvando, setSalvando] = useState(false);
  return <main className="artx-leads artx-metas">
    <div className="leads-topbar"><span>Planejamento comercial</span><span>ART X <span className="leads-topbar-caption">CRM Agência</span></span></div>
    <div className="leads-content-heading"><div><h1>Metas</h1><p>Acompanhe os objetivos e resultados mensais da ART X.</p></div><label className="metas-period">Mês e ano<input type="month" aria-label="Mês e ano das metas" min="2020-01" max="2100-12" required value={periodo} disabled={salvando} onChange={(event) => { const valor = event.target.value; if (/^\d{4}-(0[1-9]|1[0-2])$/.test(valor) && valor >= "2020-01" && valor <= "2100-12") setPeriodo(valor); }}/></label></div>
    <MetasDoPeriodo key={periodo} periodo={periodo} aoSalvar={setSalvando}/>
  </main>;
}

export default function MetasPage() {
  return <Suspense fallback={<main className="artx-leads artx-metas"><p className="metas-notice" role="status">Carregando metas...</p></main>}>
    <MetasContent />
  </Suspense>;
}

