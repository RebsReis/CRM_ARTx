
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useAuth } from "./AuthShell";

const menu = [
  { nome: "Dashboard", caminho: "/" },
  { nome: "Leads", caminho: "/leads" },
  { nome: "Clientes", caminho: "/clientes" },
  { nome: "Projetos", caminho: "/projetos" },
  { nome: "Metas", caminho: "/metas" },
  { nome: "Configurações", caminho: "/configuracoes" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { usuario, sair } = useAuth();
  const [erro, setErro] = useState("");
  const [saindo, setSaindo] = useState(false);
  async function encerrarSessao() {
    setSaindo(true); setErro("");
    try { await sair(); }
    catch { setErro("Não foi possível sair. Tente novamente."); }
    finally { setSaindo(false); }
  }

  return (
    <aside className="w-64 shrink-0 bg-slate-900 p-6 text-white">
      <h1 className="text-3xl font-bold">ART X</h1>

      <p className="mb-10 mt-2 text-sm text-slate-400">
        Gestão de Relacionamento
      </p>

      <nav className="flex flex-col gap-3">
        {menu.map((item) => {
          const ativo = pathname === item.caminho;

          return (
            <Link
              key={item.caminho}
              href={item.caminho}
              className={`rounded-lg p-3 transition-colors ${
                ativo
                  ? "bg-blue-600"
                  : "hover:bg-slate-800"
              }`}
            >
              {item.nome}
            </Link>
          );
        })}
      </nav>
      {usuario && <div className="sidebar-account"><strong>{usuario.nome}</strong><small>{usuario.tipo === "ADMIN" ? "Administrador" : "Usuário"}</small><button className="config-secondary" disabled={saindo} onClick={() => void encerrarSessao()}>{saindo ? "Saindo..." : "Sair"}</button>{erro && <p role="alert">{erro}</p>}</div>}
    </aside>
  );
}
