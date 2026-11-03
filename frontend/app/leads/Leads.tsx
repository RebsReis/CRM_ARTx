
"use client";
import {
  DndContext,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";

import CreateLeadModal from "../../components/CreateLeadModal";
import LeadCard from "../../components/LeadCard";
import KanbanColumn from "../../components/KanbanColumn";

import { useEffect, useState } from "react";
import "./leads.css";

type Lead = {
  id: number;
  nome_empresa: string;
  nicho: string | null;
  telefone: string | null;
  email: string | null;
  fase: string;
  observacao: string | null;
};

const etapas = [
  {
    nome: "Prospectar",
    codigo: "PROSPECTAR",
    cor: "bg-slate-500",
  },
  {
    nome: "Follow-up",
    codigo: "FOLLOW_UP",
    cor: "bg-blue-500",
  },
  {
    nome: "Reunião Marcada",
    codigo: "REUNIAO_MARCADA",
    cor: "bg-green-500",
  },
  {
    nome: "Remarketing Futuro",
    codigo: "REMARKETING_FUTURO",
    cor: "bg-purple-500",
  },];

export default function LeadsPage() {
  const [salvandoEdicao, setSalvandoEdicao] = useState(false);
  const [excluindo, setExcluindo] = useState<number | null>(null);
  const [busca, setBusca] = useState("");
  const [filtroEtapa, setFiltroEtapa] = useState("");
  const [leads, setLeads] = useState<Lead[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [modalAberto, setModalAberto] = useState(false);
  const [leadEditando, setLeadEditando] = useState<Lead | null>(null);
    const [leadParaFechar, setLeadParaFechar] = useState<Lead | null>(null);
    const [valorContrato, setValorContrato] = useState("");
async function alterarFaseLead(leadId: number, novaFase: string) {
  try {
   const resposta = await fetch(
  `/api/crm/leads/${leadId}/fase`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ fase: novaFase }),
      }
    );

    if (!resposta.ok) {
      const detalhe = await resposta.text();

      console.error(
        "Erro do FastAPI:",
        resposta.status,
        detalhe
      );

      throw new Error(
        `Erro ${resposta.status}: ${detalhe}`
      );
    }

    setLeads((anteriores) =>
      anteriores.map((lead) =>
        lead.id === leadId
          ? { ...lead, fase: novaFase }
          : lead
      )
    );

    console.log("Etapa atualizada com sucesso!");

  } catch (erro) {
    console.error("Falha ao alterar etapa:", erro);
    alert("Não foi possível alterar a etapa do lead.");
  }
}


  useEffect(() => {
    async function carregarLeads() {
      try {
        const resposta = await fetch(
          "/api/crm/leads",
          { cache: "no-store" }
        );

        if (!resposta.ok) {
          throw new Error(`Erro HTTP ${resposta.status}`);
        }

        const dados: Lead[] = await resposta.json();

        setLeads(dados);
        setErro("");
      } catch (error) {
        console.error("Erro ao carregar leads:", error);
        setErro(
          "Não foi possível carregar os leads. Verifique se o FastAPI está funcionando."
        );
      } finally {
        setCarregando(false);
      }
    }

    carregarLeads();
  }, []);

  

async function aoSoltarLead(event: DragEndEvent) {
  const { active, over } = event;

  console.log("ARRASTOU:", active.id, "SOLTOU EM:", over?.id);

  if (!over) return;

  // Converte "lead-5" em 5
  const leadId = Number(String(active.id).replace("lead-", ""));

  if (Number.isNaN(leadId)) return;

  const fasesValidas = [
    "PROSPECTAR",
    "FOLLOW_UP",
    "REUNIAO_MARCADA",
    "REMARKETING_FUTURO",
  ];

  const novaFase = String(over.id);

  if (!fasesValidas.includes(novaFase)) return;

  const leadAtual = leads.find((lead) => lead.id === leadId);

  if (!leadAtual || leadAtual.fase === novaFase) return;

  await alterarFaseLead(leadId, novaFase);
}

async function salvarEdicaoLead() {
  if (!leadEditando || salvandoEdicao) return;
  if (!leadEditando.nome_empresa.trim()) { alert("Informe o nome da empresa."); return; }
  setSalvandoEdicao(true);
  try {
    const { nome_empresa, nicho, telefone, email, observacao } = leadEditando;
    const resposta = await fetch(`/api/crm/leads/${leadEditando.id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome_empresa: nome_empresa.trim(), nicho, telefone, email, observacao }),
    });
    if (!resposta.ok) { const erro = await resposta.json(); throw new Error(typeof erro.detail === "string" ? erro.detail : "Dados invalidos para editar o lead."); }
    const atualizado: Lead = await resposta.json();
    setLeads((anteriores) => anteriores.map((lead) => lead.id === atualizado.id ? atualizado : lead));
    setLeadEditando(null);
  } catch (erro) { alert(erro instanceof Error ? erro.message : "Erro ao editar lead."); }
  finally { setSalvandoEdicao(false); }
}

async function excluirLead(lead: Lead) {
  if (excluindo !== null || !window.confirm(`Excluir o lead "${lead.nome_empresa}"? Esta acao nao pode ser desfeita.`)) return;
  setExcluindo(lead.id);
  try {
    const resposta = await fetch(`/api/crm/leads/${lead.id}`, { method: "DELETE" });
    if (!resposta.ok) { const erro = await resposta.json(); throw new Error(typeof erro.detail === "string" ? erro.detail : "Erro ao excluir lead."); }
    setLeads((anteriores) => anteriores.filter((item) => item.id !== lead.id));
  } catch (erro) { alert(erro instanceof Error ? erro.message : "Erro ao excluir lead."); }
  finally { setExcluindo(null); }
}

async function confirmarContrato() {
  if (!leadParaFechar) return;

  const valor = Number(valorContrato);

  if (!Number.isFinite(valor) || valor <= 0) {
    alert("Informe um valor mensal válido.");
    return;
  }

  try {
    const resposta = await fetch(
      `/api/crm/leads/${leadParaFechar.id}/fechar`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          valor_mensal: valor,
        }),
      }
    );

    if (!resposta.ok) {
      const detalhe = await resposta.text();
      throw new Error(detalhe);
    }

    setLeads((anteriores) =>
      anteriores.filter(
        (lead) => lead.id !== leadParaFechar.id
      )
    );

    setLeadParaFechar(null);
    setValorContrato("");

    alert("Contrato fechado com sucesso! Cliente cadastrado.");
  } catch (erro) {
    console.error("Erro ao fechar contrato:", erro);
    alert("Não foi possível fechar o contrato. Verifique o FastAPI.");
  }
}

  return (
    <main className="artx-leads">
      <div className="leads-topbar"><span className="leads-topbar-mark"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg></span><span>ART X <span className="leads-topbar-caption">CRM Ag&ecirc;ncia</span></span></div>
      <div className="leads-content-heading">
        <div><h1>Leads</h1><p>Funil de vendas &mdash; arraste cards entre as colunas.</p></div>
        <div className="leads-heading-actions"><span className="leads-total">Total: <strong>{leads.length}</strong></span><button type="button" onClick={() => setModalAberto(true)} className="leads-new">+ Novo lead</button></div>
      </div>
      <div className="leads-filters">
        <div className="leads-search"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></svg><input aria-label="Buscar por empresa ou nicho" placeholder="Buscar por empresa ou nicho..." value={busca} onChange={(e) => setBusca(e.target.value)} /></div>
        <select aria-label="Filtrar por etapa" value={filtroEtapa} onChange={(e) => setFiltroEtapa(e.target.value)}><option value="">Todas as etapas</option>{etapas.map((etapa) => <option key={etapa.codigo} value={etapa.codigo}>{etapa.nome}</option>)}</select>
      </div>

      {carregando && (
        <p className="mb-6 text-slate-500">
          Carregando leads...
        </p>
      )}

      {erro && (
        <div className="mb-6 rounded-lg bg-red-50 p-4 text-red-600">
          {erro}
        </div>
      )}

      <DndContext
            collisionDetection={closestCenter}
            onDragEnd={aoSoltarLead}
>
     <div className="leads-board">
        {etapas.filter((etapa) => !filtroEtapa || etapa.codigo === filtroEtapa).map((etapa) => {
          const leadsDaEtapa = leads.filter(
            (lead) => lead.fase === etapa.codigo && `${lead.nome_empresa} ${lead.nicho ?? ""}`.toLocaleLowerCase("pt-BR").includes(busca.trim().toLocaleLowerCase("pt-BR"))
          );

          return (
            <KanbanColumn
            key={etapa.codigo}
                id={etapa.codigo}
>
            
              <div className="leads-column-heading">


                <h2 className="font-semibold">
                  {etapa.nome}
                </h2>

                <span className="ml-auto rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                  {leadsDaEtapa.length}
                </span>
              </div>

              <div className="flex flex-col gap-3">
                {leadsDaEtapa.length === 0 && !carregando && (
                  <div className="rounded-lg border-2 border-dashed border-slate-200 p-5 text-center text-sm text-slate-400">
                    Nenhum lead nesta etapa
                  </div>
                )}

                {leadsDaEtapa.map((lead) => (
                  <LeadCard 
                  key={lead.id} id={lead.id}
                  >
                    <div className="lead-title-row">
                      <span className="lead-company-icon"><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="3" width="14" height="18" rx="1"/><path d="M9 7h1m4 0h1M9 11h1m4 0h1M9 15h1m4 0h1M10 21v-3h4v3"/></svg></span>
                      <div className="lead-company"><h3>{lead.nome_empresa}</h3>{lead.nicho && <p>{lead.nicho}</p>}</div>
                      <details className="lead-actions" onKeyDown={(e) => { if (e.key === "Escape") e.currentTarget.open = false; }}>
                        <summary className="lead-menu" aria-label={`Opcoes do lead ${lead.nome_empresa}`}><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="5" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="12" cy="19" r="1"/></svg></summary>
                        <div className="lead-actions-popup">
                          <button type="button" onClick={(e) => { e.currentTarget.closest("details")?.removeAttribute("open"); setLeadEditando({ ...lead }); }}>Editar</button>
                          <button type="button" className="lead-delete" disabled={excluindo !== null} onClick={(e) => { e.currentTarget.closest("details")?.removeAttribute("open"); void excluirLead(lead); }}>Excluir</button>
                        </div>
                      </details>
                    </div>
                    {lead.telefone && <a className="lead-phone" href={`tel:${lead.telefone}`}><svg aria-hidden="true" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 2 .7 2.9a2 2 0 0 1-.5 2.1L8 10a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.5c.9.3 1.9.6 2.9.7a2 2 0 0 1 1.7 2Z"/></svg> {lead.telefone}</a>}
                    {lead.email && <a className="lead-email" href={`mailto:${lead.email}`}>{lead.email}</a>}
                    {lead.observacao && <p className="lead-notes">{lead.observacao}</p>}
                    {lead.fase === "REUNIAO_MARCADA" && (
                        <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            setLeadParaFechar(lead);
                            setValorContrato("");
                        }}
                          aria-label={`Fechar contrato com ${lead.nome_empresa}`}
                          title="Fechar contrato"
                          className="lead-close-contract"
                    >
                          <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m11 17 2 2a1.4 1.4 0 0 0 2-2m-1-3 2.5 2.5a1.4 1.4 0 0 0 2-2L13 9l-1 .9a2 2 0 0 1-3-2.6l2.5-2.5a3 3 0 0 1 3-.6L19 6m0 8 2-1V5l-2 1v8ZM5 6 3 5v8l2 1V6Zm0 0h4m-4 8 5 5a1.4 1.4 0 0 0 2-2"/></svg>
                        </button>
                    
                    )}
                  </LeadCard>
                ))}
              </div>

            </KanbanColumn>
          );

        })}
        </div>
      </DndContext>
      
{modalAberto && <CreateLeadModal fechar={() => setModalAberto(false)} aoCriar={(lead) => setLeads((anteriores) => [...anteriores, lead])}/>}

{leadParaFechar && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">

      <h2 className="text-2xl font-bold text-slate-900">
        Fechar contrato
      </h2>

      <p className="mt-3 text-slate-600">
        Empresa: <strong>{leadParaFechar.nome_empresa}</strong>
      </p>

      <div className="mt-6">
        <label className="mb-2 block text-sm font-medium">
          Valor mensal do contrato (R$)
        </label>

        <input
          type="number"
          min="0.01"
          step="0.01"
          value={valorContrato}
          onChange={(e) => setValorContrato(e.target.value)}
          placeholder="Ex.: 1500.00"
          className="w-full rounded-lg border border-slate-300 p-3"
        />
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          onClick={() => setLeadParaFechar(null)}
          className="rounded-lg border border-slate-300 px-4 py-2"
        >
          Cancelar
        </button>

        <button

                type="button"
                onClick={confirmarContrato}
                className="rounded-lg bg-green-600 px-5 py-2 text-white hover:bg-green-700"
                >
                Confirmar contrato
        </button>
       
      </div>

    </div>
  </div>
)}
{/* Modal de edição do lead */}
{leadEditando && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
      <h2 className="mb-6 text-2xl font-bold text-slate-900">
        Editar lead
      </h2>

      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">
            Nome da empresa
          </label>
          <input
            type="text"
            value={leadEditando.nome_empresa}
            onChange={(e) =>
              setLeadEditando({
                ...leadEditando,
                nome_empresa: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            Nicho
          </label>
          <input
            type="text"
            value={leadEditando.nicho ?? ""}
            onChange={(e) =>
              setLeadEditando({
                ...leadEditando,
                nicho: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            Telefone
          </label>
          <input
            type="tel"
            value={leadEditando.telefone ?? ""}
            onChange={(e) =>
              setLeadEditando({
                ...leadEditando,
                telefone: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            E-mail
          </label>
          <input
            type="email"
            value={leadEditando.email ?? ""}
            onChange={(e) =>
              setLeadEditando({
                ...leadEditando,
                email: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            Observações
          </label>
          <textarea
            rows={3}
            value={leadEditando.observacao ?? ""}
            onChange={(e) =>
              setLeadEditando({
                ...leadEditando,
                observacao: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          onClick={() => setLeadEditando(null)}
          className="rounded-lg border border-slate-300 px-4 py-2"
        >
          Cancelar
        </button>

        <button
          type="button"
          onClick={salvarEdicaoLead}
          disabled={salvandoEdicao}
          className="rounded-lg bg-blue-600 px-5 py-2 font-medium text-white hover:bg-blue-700"
        >
          Salvar alterações
        </button>
      </div>
    </div>
  </div>
)}
    </main>
  );
}


