"use client";

import KanbanColumn from "@/components/KanbanColumn";
import LeadCard from "@/components/LeadCard";
import {
  DndContext,
  closestCenter,
  type DragEndEvent,
} from "@dnd-kit/core";
import { Suspense, useEffect, useEffectEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { selecionarProjetos, situacaoPrazo } from "../../lib/projetos";
import { formatarData } from "../../lib/datas";
import "../leads/leads.css";
import "./projetos.css";

type Projeto = {
  id: number;
  cliente_id: number;
  nome_projeto: string;
  prazo: string | null;
  prioridade: string;
  status: string;
  observacao: string | null;
};

type Cliente = {
  id: number;
  nome_empresa: string;
  status: string;
};

const API = "/api/crm";

const etapas = [
  {
    codigo: "PENDENTE",
    nome: "Pendente",
    cor: "bg-slate-500",
  },
  {
    codigo: "EM_ANDAMENTO",
    nome: "Em andamento",
    cor: "bg-blue-500",
  },
  {
    codigo: "FINALIZADA",
    nome: "Concluído",
    cor: "bg-green-500",
  },
];

function ProjetosContent() {
  const parametros = useSearchParams();
  const router = useRouter();
  const filtroEtapa = etapas.some((etapa) => etapa.codigo === parametros.get("status")) ? parametros.get("status")! : "";
  const filtroPrazo = parametros.get("prazo") ?? "";
  const [hoje, setHoje] = useState("");
  useEffect(() => {
    const atualizar = () => setHoje(new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date()));
    const inicio = window.setTimeout(atualizar, 0);
    const intervalo = window.setInterval(atualizar, 60000);
    return () => { window.clearTimeout(inicio); window.clearInterval(intervalo); };
  }, []);
  function filtrar(chave: string, valor: string) {
    const consulta = new URLSearchParams(parametros.toString());
    if (valor) consulta.set(chave, valor); else consulta.delete(chave);
    router.replace(`/projetos${consulta.size ? `?${consulta}` : ""}`, { scroll: false });
  }
  const [busca, setBusca] = useState("");
  const [projetos, setProjetos] = useState<Projeto[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [projetoChecklist, setProjetoChecklist] = useState<Projeto | null>(null);
  const [projetoEditando, setProjetoEditando] = useState<Projeto | null>(null);
  const [progressoProjetos, setProgressoProjetos] = useState<
  Record<number, { total: number; concluidas: number }>
>({});
  type Tarefa = {
  id: number;
  descricao: string;
  ordem: number;
  concluido: boolean;
};

const [tarefas, setTarefas] = useState<Tarefa[]>([]);
const [carregandoTarefas, setCarregandoTarefas] = useState(false);
const [modalAberto, setModalAberto] = useState(false);
const [salvando, setSalvando] = useState(false);
const [erro, setErro] = useState("");
const [novaTarefa, setNovaTarefa] = useState("");
const [salvandoTarefa, setSalvandoTarefa] = useState(false);

const [tarefaEditando, setTarefaEditando] = useState<number | null>(null);
const [descricaoEditada, setDescricaoEditada] = useState("");
  

  const [novoProjeto, setNovoProjeto] = useState({
    cliente_id: "",
    nome_projeto: "",
    prazo: "",
    prioridade: "MEDIA",
    status: "PENDENTE",
    observacao: "",
  });

async function carregarProgressoProjetos(listaProjetos: Projeto[]) {
  try {
    const resultados = await Promise.all(
      listaProjetos.map(async (projeto) => {
        const resposta = await fetch(
          `${API}/projetos/${projeto.id}/checklist`
        );

        if (!resposta.ok) {
          throw new Error(
            `Erro ao carregar checklist do projeto ${projeto.id}`
          );
        }

        const tarefas = await resposta.json();

        return {
          projetoId: projeto.id,
          total: tarefas.length,
          concluidas: tarefas.filter(
            (tarefa: { concluido: boolean }) => tarefa.concluido
          ).length,
        };
      })
    );

    const novoProgresso: Record<
      number,
      { total: number; concluidas: number }
    > = {};

    resultados.forEach((resultado) => {
      novoProgresso[resultado.projetoId] = {
        total: resultado.total,
        concluidas: resultado.concluidas,
      };
    });

    setProgressoProjetos(novoProgresso);
  } catch (erro) {
    console.error("Erro ao carregar progresso dos projetos:", erro);
  }
}

  async function carregarDados() {
    try {
      setErro("");

      const [resProjetos, resClientes] = await Promise.all([
        fetch(`${API}/projetos`),
        fetch(`${API}/clientes`),
      ]);

      if (!resProjetos.ok || !resClientes.ok) {
        throw new Error("Falha ao carregar dados.");
      }

      const dadosProjetos = await resProjetos.json();

        setProjetos(dadosProjetos);
        setClientes(await resClientes.json());

await carregarProgressoProjetos(dadosProjetos);
    } catch (error) {
      console.error(error);
      setErro("Não foi possível carregar os projetos.");
    }
  }

  const carregarDadosIniciais = useEffectEvent(() => { carregarDados(); });
  useEffect(() => {
    const inicio = window.setTimeout(carregarDadosIniciais, 0);
    return () => window.clearTimeout(inicio);
  }, []);

  async function salvarProjeto() {
    if (!novoProjeto.cliente_id || !novoProjeto.nome_projeto.trim()) {
      alert("Selecione um cliente e informe o nome do projeto.");
      return;
    }

    setSalvando(true);

    try {
      const resposta = await fetch(`${API}/projetos`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          cliente_id: Number(novoProjeto.cliente_id),
          nome_projeto: novoProjeto.nome_projeto.trim(),
          prazo: novoProjeto.prazo || null,
          prioridade: novoProjeto.prioridade,
          status: novoProjeto.status,
          observacao: novoProjeto.observacao,
        }),
      });

      if (!resposta.ok) {
        throw new Error(await resposta.text());
      }

      await carregarDados();

      setModalAberto(false);
      setNovoProjeto({
        cliente_id: "",
        nome_projeto: "",
        prazo: "",
        prioridade: "MEDIA",
        status: "PENDENTE",
        observacao: "",
      });

      alert("Projeto cadastrado com sucesso!");
    } catch (error) {
      console.error(error);
      alert("Não foi possível cadastrar o projeto.");
    } finally {
      setSalvando(false);
    }
  }

  function nomeCliente(clienteId: number) {
    return (
      clientes.find((cliente) => cliente.id === clienteId)
        ?.nome_empresa ?? `Cliente #${clienteId}`
    );
  }

  async function aoSoltarProjeto(event: DragEndEvent) {
  const { active, over } = event;
  if (!over) return;

  const projetoId = Number(
  String(active.id).replace("lead-", "")
);

  const projeto = projetos.find(
    (item) => item.id === projetoId
  );

  if (!projeto) return;

  const destinoId = String(over.id);

  // Verifica se o destino é uma coluna
  let novoStatus = etapas.find(
    (etapa) => etapa.codigo === destinoId
  )?.codigo;

  // Se o destino for outro card, identifica sua coluna
  if (!novoStatus) {
    const projetoDestino = projetos.find(
      (item) => item.id === Number(destinoId.replace("lead-", ""))
    );

    novoStatus = projetoDestino?.status;
  }

  if (!novoStatus || projeto.status === novoStatus) {
    return;
  }

  try {
    const resposta = await fetch(
      `${API}/projetos/${projetoId}/status`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          status: novoStatus,
        }),
      }
    );

      if (!resposta.ok) {
        const dados = await resposta.json().catch(() => null);
        throw new Error(typeof dados?.detail === "string" ? dados.detail : `Erro ao atualizar o status (HTTP ${resposta.status}).`);
    }

    await carregarDados();
  } catch (error) {
    console.error(error);
      alert(error instanceof Error ? error.message : "Não foi possível mover o projeto.");
  }
}
async function abrirChecklist(projeto: Projeto) {
  setProjetoChecklist(projeto);
  setTarefas([]);
  setCarregandoTarefas(true);

  try {
    const resposta = await fetch(
      `${API}/projetos/${projeto.id}/checklist`
    );

    if (!resposta.ok) {
      throw new Error("Erro ao buscar tarefas");
    }

    const dados = await resposta.json();
    setTarefas(dados);
  } catch (erro) {
    console.error(erro);
    alert("Não foi possível carregar o checklist.");
  } finally {
    setCarregandoTarefas(false);
  }
}

async function adicionarTarefa() {
  if (!projetoChecklist || !novaTarefa.trim()) return;

  setSalvandoTarefa(true);

  try {
    const resposta = await fetch(
      `${API}/projetos/${projetoChecklist.id}/checklist`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          descricao: novaTarefa.trim(),
          ordem: tarefas.length + 1,
        }),
      }
    );

    if (!resposta.ok) {
      throw new Error("Erro ao adicionar tarefa");
    }

    const lista = await fetch(
      `${API}/projetos/${projetoChecklist.id}/checklist`
    );

    if (!lista.ok) {
      throw new Error("Erro ao atualizar checklist");
    }

    setTarefas(await lista.json());
    setNovaTarefa("");
  } catch (erro) {
    console.error(erro);
    alert("Não foi possível adicionar a tarefa.");
  } finally {
    setSalvandoTarefa(false);
  }
}

async function alternarConclusao(tarefa: Tarefa) {
  if (!projetoChecklist) return;

  try {
    const resposta = await fetch(
      `${API}/checklist/${tarefa.id}/concluir`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          concluido: !tarefa.concluido,
        }),
      }
    );

    if (!resposta.ok) {
      throw new Error("Erro ao atualizar tarefa");
    }

    const lista = await fetch(
      `${API}/projetos/${projetoChecklist.id}/checklist`
    );

    if (!lista.ok) {
      throw new Error("Erro ao recarregar tarefas");
    }

    setTarefas(await lista.json());
  } catch (erro) {
    console.error(erro);
    alert("Não foi possível atualizar a tarefa.");
  }
}

async function excluirTarefa(tarefa: Tarefa) {
  const confirmou = window.confirm(
    `Deseja realmente excluir a tarefa "${tarefa.descricao}"?`
  );

  if (!confirmou) return;

  try {
    const resposta = await fetch(
      `${API}/checklist/${tarefa.id}`,
      {
        method: "DELETE",
      }
    );

    if (!resposta.ok) {
      throw new Error("Não foi possível excluir a tarefa.");
    }

    setTarefas((anteriores) =>
      anteriores.filter((item) => item.id !== tarefa.id)
    );
  } catch (erro) {
    alert("Erro ao excluir a tarefa. Tente novamente.");
    console.error(erro);
  }
}

async function salvarEdicaoTarefa(tarefa: Tarefa) {
  const descricao = descricaoEditada.trim();

  if (!descricao) {
    alert("Digite uma descrição para a tarefa.");
    return;
  }

  try {
    const resposta = await fetch(
      `${API}/checklist/${tarefa.id}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          descricao: descricao,
        }),
      }
    );

    if (!resposta.ok) {
      throw new Error("Erro ao editar tarefa");
    }

    setTarefas((anteriores) =>
      anteriores.map((item) =>
        item.id === tarefa.id
          ? { ...item, descricao }
          : item
      )
    );

    setTarefaEditando(null);
    setDescricaoEditada("");
  } catch (erro) {
    console.error(erro);
    alert("Não foi possível salvar a edição.");
  }
}

async function salvarAlteracoesProjeto() {
  if (!projetoEditando) return;

  try {
    const resposta = await fetch(
      `${API}/projetos/${projetoEditando.id}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          cliente_id: projetoEditando.cliente_id,
          nome_projeto: projetoEditando.nome_projeto,
          prazo: projetoEditando.prazo || null,
          prioridade: projetoEditando.prioridade,
          observacao: projetoEditando.observacao || "",
        }),
      }
    );

    if (!resposta.ok) {
      throw new Error("Não foi possível atualizar o projeto.");
    }

    await carregarDados();
    setProjetoEditando(null);
    alert("Projeto atualizado com sucesso!");
  } catch (erro) {
    console.error(erro);
    alert("Erro ao salvar as alterações do projeto.");
  }
}
  return (
    <main className="artx-leads artx-projetos">
      <div className="leads-topbar"><span className="leads-topbar-mark"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg></span><span>ART X <span className="leads-topbar-caption">CRM Ag&ecirc;ncia</span></span></div>
      <div className="leads-content-heading"><div><h1>Projetos</h1><p>Organize os projetos e servi&ccedil;os da ART X.</p></div><div className="leads-heading-actions"><span className="leads-total">Total: <strong>{projetos.length}</strong></span><button type="button" className="leads-new" onClick={() => setModalAberto(true)}>+ Novo projeto</button></div></div>
      <div className="mt-8 grid gap-5 sm:grid-cols-3">
        {["PENDENTE", "EM_ANDAMENTO", "FINALIZADA"].map(
          (status) => (
            <Link
              key={status}
              href={`/projetos?status=${status}`}
              className={`projeto-indicador rounded-xl bg-white p-6 shadow-sm ${filtroEtapa === status ? "projeto-indicador-ativo" : ""}`}
            >
              <p className="text-slate-500">
                {etapas.find((etapa) => etapa.codigo === status)?.nome}
              </p>

              <p className="mt-2 text-3xl font-bold">
                {projetos.filter((p) => p.status === status).length}
              </p>
            </Link>
          )
        )}
      </div>

      <h2 className="mt-10 text-xl font-bold">
        Projetos cadastrados
      </h2>

      {erro && (
        <p className="mt-4 text-red-600">{erro}</p>
      )}

<div className="leads-filters projetos-filters">
        <div className="leads-search"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></svg><input aria-label="Buscar por projeto ou cliente" placeholder="Buscar por projeto ou cliente..." value={busca} onChange={(e) => setBusca(e.target.value)} /></div>
        <select aria-label="Filtrar por etapa" value={filtroEtapa} onChange={(e) => filtrar("status", e.target.value)}><option value="">Todas as etapas</option>{etapas.map((etapa) => <option key={etapa.codigo} value={etapa.codigo}>{etapa.nome}</option>)}</select>
        <select aria-label="Filtrar por prazo" value={filtroPrazo} onChange={(e) => filtrar("prazo", e.target.value)}><option value="">Todos os prazos</option><option value="urgentes">Vencidos e entrega hoje</option><option value="vencidos">Prazo vencido</option><option value="hoje">Entrega hoje</option></select>
        {(filtroEtapa || filtroPrazo || busca) && <button type="button" className="config-secondary" onClick={() => { setBusca(""); router.replace("/projetos", { scroll: false }); }}>Limpar filtros</button>}
      </div>
<DndContext
  collisionDetection={closestCenter}
  onDragEnd={aoSoltarProjeto}
>
  <div className="projetos-board">
    {etapas.filter((etapa) => !filtroEtapa || etapa.codigo === filtroEtapa).map((etapa) => {
      const projetosDaEtapa = selecionarProjetos(projetos.filter(
        (projeto) => projeto.status === etapa.codigo && `${projeto.nome_projeto} ${nomeCliente(projeto.cliente_id)}`.toLocaleLowerCase("pt-BR").includes(busca.trim().toLocaleLowerCase("pt-BR"))
      ), hoje, filtroPrazo);

      return (
        <KanbanColumn key={etapa.codigo} id={etapa.codigo}>
          <div className="mb-5 flex items-center gap-3">
            <div
              className={`h-3 w-3 rounded-full ${etapa.cor}`}
            />

            <h2 className="font-semibold text-slate-900">
              {etapa.nome}
            </h2>

            <span className="ml-auto rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
              {projetosDaEtapa.length}
            </span>
          </div>

          <div className="space-y-3">
            {projetosDaEtapa.length === 0 && (
              <div className="rounded-lg border-2 border-dashed border-slate-200 p-5 text-center text-sm text-slate-400">
                Nenhum projeto nesta etapa
              </div>
            )}

            {projetosDaEtapa.map((projeto) => (
              <LeadCard key={projeto.id} id={projeto.id}>
                <div className={situacaoPrazo(projeto, hoje) !== "normal" ? "projeto-alerta" : undefined}>
                {situacaoPrazo(projeto, hoje) !== "normal" && <p className="projeto-alerta-label">{situacaoPrazo(projeto, hoje) === "vencido" ? "Prazo vencido" : "Entrega hoje"}</p>}
                <h3 className="font-semibold text-slate-900">
                  {projeto.nome_projeto}
                </h3>

                <p className="mt-2 text-sm text-slate-500">
                  Cliente: {nomeCliente(projeto.cliente_id)}
                </p>

                <p className="mt-3 text-sm text-slate-600">
                  Prioridade: {projeto.prioridade}
                </p>

                <p className="mt-1 text-sm text-slate-600">
                  Prazo: {formatarData(projeto.prazo, "Não definido")}
                </p>

                {projeto.observacao && (
                  <p className="mt-3 border-t border-slate-200 pt-3 text-xs text-slate-500">
                    {projeto.observacao}
                  </p>
                )}
                {/* Progresso do projeto */}
{(() => {
  const progresso = progressoProjetos[projeto.id];

  const total = progresso?.total ?? 0;
  const concluidas = progresso?.concluidas ?? 0;

  const percentual =
    total > 0 ? Math.round((concluidas / total) * 100) : 0;

  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium text-slate-600">
          Progresso
        </span>

        <span className="text-sm font-semibold text-blue-600">
          {percentual}%
        </span>
      </div>

      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-300"
          style={{ width: `${percentual}%` }}
        />
      </div>

      <p className="mt-1 text-xs text-slate-500">
        {concluidas} de {total} tarefas concluídas
      </p>
    </div>
  );
})()}

                <div className="projeto-card-actions">
                <button
                    type="button"
                    aria-label={`Ver checklist de ${projeto.nome_projeto}`}
                    title="Ver checklist"
                    onClick={(event) => { event.stopPropagation(); void abrirChecklist(projeto); }}
                    className="projeto-icon-action text-blue-600 hover:bg-blue-50"
                    >
                    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="17" rx="2"/><rect x="9" y="2" width="6" height="4" rx="1"/><path d="m7 11 1 1 2-2m3 1h4m-10 6 1 1 2-2m3 1h4"/></svg>
                    </button>
                <button
                    type="button"
                    aria-label={`Editar projeto ${projeto.nome_projeto}`}
                    title="Editar projeto"
                    onClick={(e) => {
                        e.stopPropagation();
                        setProjetoEditando(projeto);
                    }}
                    className="projeto-icon-action text-blue-600 hover:bg-blue-50"
                    >
                    <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15l-1 6Z"/></svg>
                    </button>
                </div>
                </div>
              </LeadCard>
            ))}
          </div>
        </KanbanColumn>
      );
    })}
  </div>
</DndContext>

      {!erro && projetos.length === 0 && (
        <p className="mt-6 text-slate-500">
          Nenhum projeto cadastrado.
        </p>
      )}

      {/* Modal Novo Projeto */}
      {modalAberto && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
            <h2 className="text-2xl font-bold">
              Novo Projeto
            </h2>

            <div className="mt-6 space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium">
                  Cliente *
                </label>

                <select
                  value={novoProjeto.cliente_id}
                  onChange={(e) =>
                    setNovoProjeto({
                      ...novoProjeto,
                      cliente_id: e.target.value,
                    })
                  }
                  className="w-full rounded-lg border border-slate-300 p-3"
                >
                  <option value="">Selecione um cliente</option>

                  {clientes
                    .filter((cliente) => cliente.status === "ATIVO")
                    .map((cliente) => (
                      <option key={cliente.id} value={cliente.id}>
                        {cliente.nome_empresa}
                      </option>
                    ))}
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">
                  Nome do projeto *
                </label>

                <input
                  value={novoProjeto.nome_projeto}
                  onChange={(e) =>
                    setNovoProjeto({
                      ...novoProjeto,
                      nome_projeto: e.target.value,
                    })
                  }
                  placeholder="Ex.: Gestão de Tráfego Pago"
                  className="w-full rounded-lg border border-slate-300 p-3"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">
                  Prazo
                </label>

                <input
                  type="date"
                  value={novoProjeto.prazo}
                  onChange={(e) =>
                    setNovoProjeto({
                      ...novoProjeto,
                      prazo: e.target.value,
                    })
                  }
                  className="w-full rounded-lg border border-slate-300 p-3"
                />
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">
                  Prioridade
                </label>

                <select
                  value={novoProjeto.prioridade}
                  onChange={(e) =>
                    setNovoProjeto({
                      ...novoProjeto,
                      prioridade: e.target.value,
                    })
                  }
                  className="w-full rounded-lg border border-slate-300 p-3"
                >
                  <option value="BAIXA">Baixa</option>
                  <option value="MEDIA">Média</option>
                  <option value="ALTA">Alta</option>
                </select>
              </div>

              <div>
                <label className="mb-1 block text-sm font-medium">
                  Observações
                </label>

                <textarea
                  value={novoProjeto.observacao}
                  onChange={(e) =>
                    setNovoProjeto({
                      ...novoProjeto,
                      observacao: e.target.value,
                    })
                  }
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 p-3"
                />
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setModalAberto(false)}
                className="rounded-lg border border-slate-300 px-4 py-2"
              >
                Cancelar
              </button>

              <button
                type="button"
                disabled={salvando}
                onClick={salvarProjeto}
                className="rounded-lg bg-blue-600 px-5 py-2 font-medium text-white disabled:opacity-50"
              >
                {salvando ? "Salvando..." : "Salvar projeto"}
              </button>
            </div>
          </div>
        </div>
      )}
      {projetoChecklist && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-xl">
      <h2 className="text-2xl font-bold text-slate-900">
        Checklist do projeto
      </h2>

      <p className="mt-2 text-slate-500">
        {projetoChecklist.nome_projeto}
      </p>

      <div className="mt-5">
  <div className="mb-2 flex justify-between text-sm">
    <span className="font-medium text-slate-600">
      Progresso do projeto
    </span>

    <span className="font-semibold text-green-600">
      {tarefas.length === 0
        ? 0
        : Math.round(
            (tarefas.filter((t) => t.concluido).length /
              tarefas.length) *
              100
          )}
      %
    </span>
  </div>

  <div className="h-3 overflow-hidden rounded-full bg-slate-200">
    <div
      className="h-full rounded-full bg-green-500 transition-all duration-300"
      style={{
        width: `${
          tarefas.length === 0
            ? 0
            : (tarefas.filter((t) => t.concluido).length /
                tarefas.length) *
              100
        }%`,
      }}
    />
  </div>

  <p className="mt-2 text-xs text-slate-500">
    {tarefas.filter((t) => t.concluido).length} de{" "}
    {tarefas.length} tarefas concluídas
  </p>
</div>

   <div className="mt-6 space-y-3">
  {carregandoTarefas ? (
    <p className="text-slate-500">Carregando tarefas...</p>
  ) : tarefas.length === 0 ? (
    <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-slate-500">
      Nenhuma tarefa cadastrada neste projeto.
    </p>
  ) : (
  tarefas.map((tarefa) => (
  <div
    key={tarefa.id}
    className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3"
  >
    <label className="flex min-w-0 flex-1 cursor-pointer items-center gap-3">
      <input
        type="checkbox"
        checked={tarefa.concluido}
        onChange={() => alternarConclusao(tarefa)}
        className="h-5 w-5 accent-green-600"
      />

    {tarefaEditando === tarefa.id ? (
  <input
    type="text"
    value={descricaoEditada}
    onChange={(e) => setDescricaoEditada(e.target.value)}
    className="min-w-0 flex-1 rounded-lg border border-blue-400 p-2 text-slate-900"
    autoFocus
  />
) : (
  <span
    className={
      tarefa.concluido
        ? "flex-1 text-slate-400 line-through"
        : "flex-1 text-slate-900"
    }
  >
    {tarefa.descricao}
  </span>
)}
    
</label>
{tarefaEditando === tarefa.id ? (
  <div className="flex items-center gap-2">
    <button
      type="button"
      onClick={() => salvarEdicaoTarefa(tarefa)}
      className="text-sm font-medium text-green-600 hover:underline"
    >
      Salvar
    </button>

    <button
      type="button"
      onClick={() => {
        setTarefaEditando(null);
        setDescricaoEditada("");
      }}
      className="text-sm text-slate-500 hover:underline"
    >
      Cancelar
    </button>
  </div>
) : (
  <button
    type="button"
    onClick={() => {
      setTarefaEditando(tarefa.id);
      setDescricaoEditada(tarefa.descricao);
    }}
    className="rounded-lg px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-50"
  >
    Editar
  </button>
)}
    <button
      type="button"
      onClick={() => excluirTarefa(tarefa)}
      className="rounded-lg px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
    >
      Excluir
    </button>
  </div> 
))
    )}
</div>
      <div className="mt-5 flex gap-2">
  <input
    type="text"
    value={novaTarefa}
    onChange={(e) => setNovaTarefa(e.target.value)}
    placeholder="Digite uma nova tarefa..."
    className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2"
  />

  <button
    type="button"
    onClick={adicionarTarefa}
    disabled={salvandoTarefa || !novaTarefa.trim()}
    className="rounded-lg bg-green-600 px-4 py-2 font-medium text-white hover:bg-green-700 disabled:opacity-50"
  >
    {salvandoTarefa ? "Salvando..." : "+ Adicionar"}
  </button>
</div>
        <button
          type="button"
          onClick={() => setProjetoChecklist(null)}
          className="rounded-lg bg-blue-600 px-5 py-2 text-white hover:bg-blue-700"
        >
          Fechar
        </button>
      </div>
    </div>
  
)}
{/* Modal Editar Projeto */}
{projetoEditando && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">
      <h2 className="text-2xl font-bold text-slate-900">
        Editar projeto
      </h2>

      <div className="mt-6 space-y-4">
        <div>
          <label className="mb-1 block text-sm font-medium">
            Nome do projeto
          </label>
          <input
            type="text"
            value={projetoEditando.nome_projeto}
            onChange={(e) =>
              setProjetoEditando({
                ...projetoEditando,
                nome_projeto: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            Cliente
          </label>
          <select
            value={projetoEditando.cliente_id}
            onChange={(e) =>
              setProjetoEditando({
                ...projetoEditando,
                cliente_id: Number(e.target.value),
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          >
            {clientes.map((cliente) => (
              <option key={cliente.id} value={cliente.id}>
                {cliente.nome_empresa}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            Prazo
          </label>
          <input
            type="date"
            value={projetoEditando.prazo || ""}
            onChange={(e) =>
              setProjetoEditando({
                ...projetoEditando,
                prazo: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            Prioridade
          </label>
          <select
            value={projetoEditando.prioridade}
            onChange={(e) =>
              setProjetoEditando({
                ...projetoEditando,
                prioridade: e.target.value,
              })
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          >
            <option value="BAIXA">Baixa</option>
            <option value="MEDIA">Média</option>
            <option value="ALTA">Alta</option>
            <option value="URGENTE">Urgente</option>
          </select>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium">
            Observações
          </label>
          <textarea
            value={projetoEditando.observacao || ""}
            onChange={(e) =>
              setProjetoEditando({
                ...projetoEditando,
                observacao: e.target.value,
              })
            }
            rows={3}
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>
      </div>

      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          onClick={() => setProjetoEditando(null)}
          className="rounded-lg border border-slate-300 px-4 py-2"
        >
          Cancelar
        </button>

        <button
          type="button"
          onClick={salvarAlteracoesProjeto}
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

export default function ProjetosPage() {
  return <Suspense fallback={<main className="artx-leads artx-projetos"><p role="status">Carregando projetos...</p></main>}><ProjetosContent/></Suspense>;
}

