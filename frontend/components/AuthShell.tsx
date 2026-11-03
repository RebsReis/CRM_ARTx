"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import Sidebar from "./Sidebar";
import "../app/leads/leads.css";
import "../app/configuracoes/configuracoes.css";

export type Usuario = { id: number; nome: string; email: string; tipo: "ADMIN" | "USUARIO"; ativo: boolean; criado_em: string; status_acesso: "PENDENTE" | "APROVADO" | "RECUSADO"; email_verificado: boolean };
const paginasPublicas = new Set(["/login", "/cadastro", "/esqueci-senha", "/redefinir-senha", "/verificar-email"]);
type Auth = { usuario: Usuario | null; definirUsuario: (usuario: Usuario | null) => void; sair: () => Promise<void> };
const AuthContext = createContext<Auth | null>(null);
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("Contexto de autenticação indisponível.");
  return context;
}

// Mensagem deixada para a tela de login quando a sessao e encerrada de proposito (ex.: troca de senha).
export const AVISO_LOGIN = "artx-aviso-login";

export async function authRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/crm${path}`, { ...options, credentials: "same-origin", cache: "no-store", headers: { "Content-Type": "application/json", ...options?.headers } });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(typeof payload?.detail === "string" ? payload.detail : "Confira os dados informados e tente novamente.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export default function AuthShell({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const versaoSessao = useRef(0);
  const definirUsuario = useCallback((novo: Usuario | null) => { versaoSessao.current++; setUsuario(novo); }, []);
  const [verificando, setVerificando] = useState(true);
  const [erro, setErro] = useState("");
  const pathname = usePathname();
  const router = useRouter();
  const verificar = useCallback(async (signal?: AbortSignal) => {
    const versao = versaoSessao.current;
    try {
      const response = await fetch("/api/crm/auth/me", { credentials: "same-origin", cache: "no-store", signal });
      if (signal?.aborted || versao !== versaoSessao.current) return;
      if (response.status === 401) { setUsuario(null); setErro(""); }
      else if (response.ok) { const atual = await response.json(); if (!signal?.aborted && versao === versaoSessao.current) { setUsuario(atual); setErro(""); } }
      else setErro("Não foi possível verificar a sessão. Confira se a API está disponível.");
    } catch { if (!signal?.aborted && versao === versaoSessao.current) setErro("Não foi possível conectar ao CRM."); }
    finally { if (!signal?.aborted) setVerificando(false); }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const inicio = window.setTimeout(() => void verificar(controller.signal), 0);
    const aoVoltar = () => { if (document.visibilityState === "visible") void verificar(controller.signal); };
    window.addEventListener("focus", aoVoltar);
    const intervalo = window.setInterval(aoVoltar, 60000);
    return () => { controller.abort(); window.clearTimeout(inicio); window.removeEventListener("focus", aoVoltar); window.clearInterval(intervalo); };
  }, [verificar]);
  useEffect(() => {
    if (!verificando && !usuario && !erro && !paginasPublicas.has(pathname)) router.replace("/login");
  }, [usuario, verificando, erro, pathname, router]);
  async function sair() {
    await authRequest<void>("/auth/logout", { method: "POST" });
    definirUsuario(null); router.replace("/login"); router.refresh();
  }
  return <AuthContext.Provider value={{ usuario, definirUsuario, sair }}>
    {paginasPublicas.has(pathname) ? children : verificando || !usuario ? <main className="artx-leads auth-loading"><p role="status">{erro || "Verificando sessão..."}</p>{erro && <button className="leads-new" onClick={() => void verificar()}>Tentar novamente</button>}</main> : <div key={usuario.id} className="artx-shell flex min-h-screen bg-slate-100"><Sidebar/><div className="min-w-0 flex-1">{children}</div></div>}
  </AuthContext.Provider>;
}
