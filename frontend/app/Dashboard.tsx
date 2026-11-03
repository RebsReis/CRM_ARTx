"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import "./leads/leads.css";
import "./dashboard.css";
import { projetoConcluido, situacaoPrazo } from "../lib/projetos";

type Progresso = { faltam: number; percentual_atingido: number };
type Metas = {
  prospeccoes: Progresso & { meta_prospeccoes: number; prospeccoes_realizadas: number };
  reunioes: Progresso & { meta_reunioes: number; reunioes_realizadas: number };
  faturamento: Progresso & { meta_faturamento: number; faturamento_recorrente: number };
};
type Lead = { id: number; fase: string };
type Cliente = { id: number; status: string; valor_mensal: number | string };
type Projeto = { id: number; status: string; prazo: string | null };
const etapas = [
  { codigo: "PROSPECTAR", nome: "Prospectar" },
  { codigo: "FOLLOW_UP", nome: "Follow-up" },
  { codigo: "REUNIAO_MARCADA", nome: "Reunião marcada" },
  { codigo: "REMARKETING_FUTURO", nome: "Remarketing futuro" },
];
const moeda = (valor: number) => valor.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const numero = (valor: number) => valor.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
const hojeBrasil = () => new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
const concluido = projetoConcluido;

function Barra({ valor }: { valor: number }) {
  return <div className="dashboard-bar"><div style={{ width: `${Math.min(100, Math.max(0, valor))}%` }} /></div>;
}

export default function Dashboard() {
  const [periodo, setPeriodo] = useState(() => hojeBrasil().slice(0, 7));
  const [leads, setLeads] = useState<Lead[] | null>(null);
  const [clientes, setClientes] = useState<Cliente[] | null>(null);
  const [projetos, setProjetos] = useState<Projeto[] | null>(null);
  const [metas, setMetas] = useState<Metas | null>(null);
  const [erros, setErros] = useState<string[]>([]);
  const [erroMetas, setErroMetas] = useState("");
  const [carregando, setCarregando] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let emCurso = false;
    async function consultar<T>(rota: string): Promise<T> {
      const resposta = await fetch(`/api/crm${rota}`, { cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]) });
      if (!resposta.ok) throw new Error(String(resposta.status));
      return resposta.json();
    }
    async function carregar() {
      if (emCurso || controller.signal.aborted) return;
      emCurso = true;
      const [ano, mes] = periodo.split("-").map(Number);
      const [resLeads, resClientes, resProjetos, resMetas] = await Promise.allSettled([
        consultar<Lead[]>("/leads"), consultar<Cliente[]>("/clientes"), consultar<Projeto[]>("/projetos"),
        consultar<Metas>(`/metas/dashboard?ano=${ano}&mes=${mes}`),
      ] as const);
      if (controller.signal.aborted) return;
      setLeads(resLeads.status === "fulfilled" ? resLeads.value : null);
      setClientes(resClientes.status === "fulfilled" ? resClientes.value : null);
      setProjetos(resProjetos.status === "fulfilled" ? resProjetos.value : null);
      setMetas(resMetas.status === "fulfilled" ? resMetas.value : null);
      setErros([resLeads.status === "rejected" ? "leads" : "", resClientes.status === "rejected" ? "clientes" : "", resProjetos.status === "rejected" ? "projetos" : ""].filter(Boolean));
      setErroMetas(resMetas.status === "rejected" ? (resMetas.reason instanceof Error && resMetas.reason.message === "404" ? "Não há metas cadastradas para este período." : "Não foi possível carregar as metas do período. Verifique a API.") : "");
      setCarregando(false);
      emCurso = false;
    }
    const aoVoltar = () => { if (document.visibilityState === "visible") void carregar(); };
    void carregar();
    const intervalo = window.setInterval(aoVoltar, 10000);
    window.addEventListener("focus", aoVoltar);
    window.addEventListener("online", aoVoltar);
    document.addEventListener("visibilitychange", aoVoltar);
    return () => {
      controller.abort();
      window.clearInterval(intervalo);
      window.removeEventListener("focus", aoVoltar);
      window.removeEventListener("online", aoVoltar);
      document.removeEventListener("visibilitychange", aoVoltar);
    };
  }, [periodo]);

  const ativos = clientes?.filter((cliente) => cliente.status === "ATIVO");
  const receita = ativos?.reduce((total, cliente) => total + Number(cliente.valor_mensal), 0);
  const finalizados = projetos?.filter(concluido).length;
  const atrasados = projetos?.filter((projeto) => situacaoPrazo(projeto, hojeBrasil()) === "vencido").length;
  const kpis = [
    { titulo: "Leads no funil", valor: leads ? numero(leads.length) : "—", detalhe: "Oportunidades na base atual", link: "/leads" },
    { titulo: "Clientes ativos", valor: ativos ? numero(ativos.length) : "—", detalhe: "Contratos com status ativo", link: "/clientes" },
    { titulo: "Receita mensal recorrente", valor: receita !== undefined ? moeda(receita) : "—", detalhe: "Soma dos contratos ativos", link: "/clientes" },
    { titulo: "Ticket médio mensal", valor: receita !== undefined && ativos ? moeda(ativos.length ? receita / ativos.length : 0) : "—", detalhe: "Receita por cliente ativo", link: "/clientes" },
    { titulo: "Projetos em andamento", valor: projetos ? numero(projetos.filter((p) => p.status === "EM_ANDAMENTO").length) : "—", detalhe: "Trabalhos em execução", link: "/projetos?status=EM_ANDAMENTO" },
    { titulo: "Projetos pendentes", valor: projetos ? numero(projetos.filter((p) => p.status === "PENDENTE").length) : "—", detalhe: "Aguardando início", link: "/projetos?status=PENDENTE" },
    { titulo: "Projetos atrasados", valor: atrasados !== undefined ? numero(atrasados) : "—", detalhe: "Prazo vencido e não concluídos", link: "/projetos?prazo=vencidos", alerta: !!atrasados },
    { titulo: "Projetos concluídos", valor: finalizados !== undefined ? numero(finalizados) : "—", detalhe: projetos ? `${numero(projetos.length ? (finalizados ?? 0) / projetos.length * 100 : 0)}% dos ${projetos.length} projetos cadastrados` : "Conclusão dos projetos cadastrados", link: "/projetos?status=FINALIZADA" },
  ];
  const indicadores = metas ? [
    { titulo: "Prospecções", realizado: numero(metas.prospeccoes.prospeccoes_realizadas), meta: numero(metas.prospeccoes.meta_prospeccoes), progresso: metas.prospeccoes.percentual_atingido, falta: `${numero(metas.prospeccoes.faltam)} prospecções` },
    { titulo: "Reuniões agendadas", realizado: numero(metas.reunioes.reunioes_realizadas), meta: numero(metas.reunioes.meta_reunioes), progresso: metas.reunioes.percentual_atingido, falta: `${numero(metas.reunioes.faltam)} reuniões` },
    { titulo: "Faturamento recorrente", realizado: moeda(metas.faturamento.faturamento_recorrente), meta: moeda(metas.faturamento.meta_faturamento), progresso: metas.faturamento.percentual_atingido, falta: moeda(metas.faturamento.faltam) },
  ] : [];

  return (
    <main className="artx-leads artx-dashboard" aria-busy={carregando}>
      <div className="leads-topbar"><span className="dashboard-brand">Visão geral</span><span>ART X <span className="leads-topbar-caption">CRM Agência</span></span></div>
      <div className="leads-content-heading"><div><h1>Dashboard</h1><p>Acompanhe o comercial, os contratos e as entregas da ART X.</p></div><Link href="/leads" className="leads-new">Ver leads</Link></div>
      {carregando && <p className="dashboard-notice" role="status">Carregando indicadores...</p>}
      {erros.length > 0 && <p className="dashboard-notice dashboard-warning" role="alert">Não foi possível carregar: {erros.join(", ")}. Os indicadores indisponíveis aparecem como —.</p>}
      <div className="dashboard-section-title"><h2>Indicadores atuais</h2><span>Base atual · todos os períodos</span></div>
      <div className="dashboard-kpis">{kpis.map((kpi) => <Link href={kpi.link} className={`dashboard-card ${kpi.alerta ? "dashboard-late" : ""}`} key={kpi.titulo}><div className="dashboard-card-label">{kpi.titulo}<span aria-hidden="true">↗</span></div><p className="dashboard-value">{kpi.valor}</p><p className="dashboard-caption">{kpi.detalhe}</p></Link>)}</div>
      <section className="dashboard-funnel dashboard-card"><div className="dashboard-section-title"><h2>Distribuição do funil</h2><Link href="/leads">Abrir Kanban →</Link></div><div className="dashboard-funnel-grid">{etapas.map((etapa) => { const total = leads?.filter((lead) => lead.fase === etapa.codigo).length; const proporcao = leads?.length ? (total ?? 0) / leads.length * 100 : 0; return <div key={etapa.codigo}><div className="dashboard-funnel-label"><span>{etapa.nome}</span><strong>{total ?? "—"}</strong></div><Barra valor={proporcao}/><p className="dashboard-caption">{leads ? `${numero(proporcao)}% dos leads atuais` : "Dados indisponíveis"}</p></div>; })}</div></section>
      <section className="dashboard-targets"><div className="dashboard-section-title"><div><h2>Metas do mês</h2><p className="dashboard-caption">Funil atual comparado com as metas do mês; faturamento do período</p></div><label className="dashboard-period">Período<input type="month" aria-label="Período das metas" min="2020-01" max="2100-12" value={periodo} onChange={(e) => { if (/^\d{4}-\d{2}$/.test(e.target.value)) { setPeriodo(e.target.value); setMetas(null); setErroMetas(""); setCarregando(true); } }}/></label></div>
        {erroMetas && <p className="dashboard-notice" role="status">{erroMetas}</p>}
        <div className="dashboard-goals">{indicadores.map((item) => <article className="dashboard-card" key={item.titulo}><h3 className="dashboard-card-label">{item.titulo}</h3><p className="dashboard-goal-value">{item.realizado}<span> / {item.meta}</span></p><p className="dashboard-accent">{numero(item.progresso)}% da meta</p><Barra valor={item.progresso}/><p className="dashboard-caption">{item.progresso >= 100 ? "Meta atingida" : `Faltam ${item.falta}`}</p></article>)}</div>
      </section>
    </main>
  );
}
