"use client";

import { useEffect, useState } from "react";
import CreateLeadModal from "../../components/CreateLeadModal";
import { formatarData } from "../../lib/datas";
import "../leads/leads.css";
import "./clientes.css";

type Cliente = {
  id: number;
  nome_empresa: string;
  nicho: string | null;
  telefone: string | null;
  email: string | null;
  valor_mensal: number;
  data_inicio: string;
  data_encerramento: string | null;
  status: string;
};

export default function ClientesPage() {
  const [criandoLead, setCriandoLead] = useState(false);
  const [avisoLead, setAvisoLead] = useState("");
  const [busca, setBusca] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);
  const [clienteEditando, setClienteEditando] = useState<Cliente | null>(null);
  const [salvandoEdicao, setSalvandoEdicao] = useState(false);

  useEffect(() => {
    async function carregarClientes() {
      try {
        const resposta = await fetch(
          "/api/crm/clientes"
        );

        if (!resposta.ok) {
          throw new Error("Erro ao buscar clientes");
        }

        const dados = await resposta.json();
        setClientes(dados);
      } catch {
        setErro("Não foi possível carregar os clientes.");
      } finally {
        setCarregando(false);
      }
    }

    carregarClientes();
  }, []);

  const faturamento = clientes
    .filter((cliente) => cliente.status === "ATIVO")
    .reduce(
      (total, cliente) => total + Number(cliente.valor_mensal),
      0
    );

  const formatarMoeda = (valor: number) =>
    valor.toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL",
    });

    async function encerrarContrato(cliente: Cliente) {
  const confirmar = window.confirm(
    `Deseja realmente encerrar o contrato de ${cliente.nome_empresa}?`
  );

  if (!confirmar) return;

  try {
    const resposta = await fetch(
      `/api/crm/clientes/${cliente.id}/encerrar`,
      {
        method: "PATCH",
      }
    );

    if (!resposta.ok) {
      const detalhe = await resposta.text();
      throw new Error(detalhe);
    }

    const encerrado: { data_encerramento: string | null } = await resposta.json();
    setClientes((anteriores) =>
      anteriores.map((item) =>
        item.id === cliente.id
          ? { ...item, status: "INATIVO", data_encerramento: encerrado.data_encerramento }
          : item
      )
    );

    alert("Contrato encerrado com sucesso!");
  } catch (erro) {
    console.error("Erro ao encerrar contrato:", erro);
    alert("Não foi possível encerrar o contrato.");
  }
}

async function salvarEdicao() {
  if (!clienteEditando || salvandoEdicao) return;

  if (!clienteEditando.nome_empresa.trim()) {
    alert("Informe o nome da empresa.");
    return;
  }

  if (
    !Number.isFinite(Number(clienteEditando.valor_mensal)) ||
    Number(clienteEditando.valor_mensal) <= 0
  ) {
    alert("Informe um valor mensal válido.");
    return;
  }

  setSalvandoEdicao(true);

  try {
    const resposta = await fetch(
      `/api/crm/clientes/${clienteEditando.id}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          nome_empresa: clienteEditando.nome_empresa,
          nicho: clienteEditando.nicho,
          telefone: clienteEditando.telefone,
          email: clienteEditando.email,
          valor_mensal: Number(clienteEditando.valor_mensal),
        }),
      }
    );

    if (!resposta.ok) {
      const dados = await resposta.json().catch(() => null);
      alert(typeof dados?.detail === "string" ? dados.detail : "Não foi possível atualizar o cliente.");
      return;
    }

    const atualizado = await resposta.json();

    setClientes((anteriores) =>
      anteriores.map((cliente) =>
        cliente.id === atualizado.id
          ? { ...cliente, ...atualizado }
          : cliente
      )
    );

    setClienteEditando(null);
    alert("Cliente atualizado com sucesso!");
  } catch (erro) {
    console.error("Erro ao editar cliente:", erro);
    alert("Não foi possível atualizar o cliente.");
  } finally {
    setSalvandoEdicao(false);
  }
}
  const clientesFiltrados = clientes.filter((cliente) =>
    (!filtroStatus || cliente.status === filtroStatus) &&
    `${cliente.nome_empresa} ${cliente.nicho ?? ""}`.toLocaleLowerCase("pt-BR").includes(busca.trim().toLocaleLowerCase("pt-BR"))
  );

  return (
    <main className="artx-leads artx-clientes">
      <div className="leads-topbar"><span className="leads-topbar-mark"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M9 4v16"/></svg></span><span>ART X <span className="leads-topbar-caption">CRM Ag&ecirc;ncia</span></span></div>
      <div className="leads-content-heading"><div><h1>Clientes</h1><p>Acompanhe os contratos e clientes da ART X.</p></div><div className="leads-heading-actions"><span className="leads-total">Total: <strong>{clientes.length}</strong></span><button type="button" className="leads-new" onClick={() => { setAvisoLead(""); setCriandoLead(true); }}>+ Criar lead</button></div></div>
      {avisoLead && <p className="config-message config-success" role="status">{avisoLead}</p>}
      <div className="mt-8 grid gap-5 sm:grid-cols-2">
        <div className="rounded-xl bg-white p-6 shadow-sm">
          <p className="text-slate-500">Clientes ativos</p>
          <h2 className="mt-2 text-3xl font-bold">
            {clientes.filter((c) => c.status === "ATIVO").length}
          </h2>
        </div>

        <div className="rounded-xl bg-white p-6 shadow-sm">
          <p className="text-slate-500">Faturamento mensal recorrente</p>
          <h2 className="mt-2 text-3xl font-bold text-green-600">
            {formatarMoeda(faturamento)}
          </h2>
        </div>
      </div>

      <h2 className="mt-10 text-xl font-bold">Clientes cadastrados</h2>
      <div className="leads-filters clientes-filters">
        <div className="leads-search"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="10.5" cy="10.5" r="7"/><path d="m16 16 5 5"/></svg><input aria-label="Buscar por empresa ou nicho" placeholder="Buscar por empresa ou nicho..." value={busca} onChange={(e) => setBusca(e.target.value)} /></div>
        <select aria-label="Filtrar por status" value={filtroStatus} onChange={(e) => setFiltroStatus(e.target.value)}><option value="">Todos os status</option><option value="ATIVO">Ativos</option><option value="INATIVO">Inativos</option></select>
      </div>

      {carregando && <p className="mt-4">Carregando clientes...</p>}
      {erro && <p className="mt-4 text-red-600">{erro}</p>}

      <div className="clientes-grid">
        {clientesFiltrados.map((cliente) => (
          <div
            key={cliente.id}
            className="rounded-xl bg-white p-6 shadow-sm"
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-bold">
                {cliente.nome_empresa}
              </h3>

              <span
                className={
                  cliente.status === "ATIVO"
                    ? "rounded-full bg-green-100 px-3 py-1 text-xs text-green-700"
                    : "cliente-status-inativo rounded-full px-3 py-1 text-xs"
                }
              >
                {cliente.status}
              </span>
            </div>

            {cliente.nicho && (
              <p className="mt-2 text-slate-500">{cliente.nicho}</p>
            )}

            {cliente.telefone && (
              <p className="mt-3 text-sm">{cliente.telefone}</p>
            )}

            {cliente.email && (
              <p className="mt-1 break-all text-sm">{cliente.email}</p>
            )}

            <div className="mt-5 border-t border-slate-200 pt-4">
              <p className="text-sm text-slate-500">Valor mensal</p>
              <p className="text-xl font-bold text-green-600">
                {formatarMoeda(Number(cliente.valor_mensal))}
              </p>

              <p className="mt-3 text-sm text-slate-500">
                Início: {formatarData(cliente.data_inicio)}
              </p>
              <p className="mt-1 text-sm text-slate-500">Fim: {cliente.data_encerramento ? formatarData(cliente.data_encerramento) : cliente.status === "ATIVO" ? "Em vigor" : "Não informado"}</p>
            <div className="cliente-card-actions">
            <button
         
                type="button"
                onClick={() => setClienteEditando({ ...cliente })}
                aria-label={`Editar cliente ${cliente.nome_empresa}`}
                title="Editar cliente"
                className="cliente-icon-action cliente-icon-edit"
                >
                <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="m15 5 4 4M4 20l4-1L20 7a2.8 2.8 0 0 0-4-4L4 15l-1 6Z"/></svg>
            </button>
            
                    {cliente.status === "ATIVO" && (
                    <button
                        type="button"
                        onClick={() => encerrarContrato(cliente)}
                        aria-label={`Encerrar contrato de ${cliente.nome_empresa}`}
                        title="Encerrar contrato"
                        className="cliente-icon-action cliente-icon-end"
                    >
                        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6m-11 5 6 6m0-6-6 6"/></svg>
                    </button>
                    )}
            </div>
            </div>
          </div>
        ))}
      </div>

      {!carregando && !erro && clientes.length > 0 && clientesFiltrados.length === 0 && <p className="clientes-empty">Nenhum cliente encontrado para os filtros selecionados.</p>}
      {!carregando && !erro && clientes.length === 0 && (
        <p className="mt-5 text-slate-500">
          Nenhum cliente cadastrado.
        </p>
      )}
      {clienteEditando && (
  <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
    <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-6 shadow-xl">

      <h2 className="mb-5 text-2xl font-bold">
        Editar cliente
      </h2>

      {([
        ["nome_empresa", "Nome da empresa"],
        ["nicho", "Nicho"],
        ["telefone", "Telefone"],
        ["email", "E-mail"],
        ["valor_mensal", "Valor mensal (R$)"],
      ] as const).map(([campo, titulo]) => (
        <div key={campo} className="mb-4">
          <label className="mb-1 block text-sm font-medium">
            {titulo}
          </label>

          <input
            type={
              campo === "valor_mensal"
                ? "number"
                : campo === "email"
                ? "email"
                : "text"
            }
            min={campo === "valor_mensal" ? "0.01" : undefined}
            step={campo === "valor_mensal" ? "0.01" : undefined}
            value={clienteEditando[campo] ?? ""}
            onChange={(e) =>
              setClienteEditando({
                ...clienteEditando,
                [campo]: e.target.value,
              } as Cliente)
            }
            className="w-full rounded-lg border border-slate-300 p-3"
          />
        </div>
      ))}

      <div className="mt-6 flex justify-end gap-3">
        <button
          type="button"
          onClick={() => setClienteEditando(null)}
          className="rounded-lg border border-slate-300 px-4 py-2"
        >
          Cancelar
        </button>

        <button
          type="button"
          onClick={salvarEdicao}
          disabled={salvandoEdicao}
          className="rounded-lg bg-blue-600 px-5 py-2 font-medium text-white disabled:opacity-50"
        >
          {salvandoEdicao ? "Salvando..." : "Salvar alterações"}
        </button>
      </div>

    </div>
  </div>
)}
    {criandoLead && <CreateLeadModal fechar={() => setCriandoLead(false)} aoCriar={(lead) => setAvisoLead(`Lead ${lead.nome_empresa} criado com sucesso. Disponível no Kanban de Leads.`)}/>}
    </main>
  );
}

