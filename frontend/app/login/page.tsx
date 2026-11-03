"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authRequest, useAuth, type Usuario } from "../../components/AuthShell";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  const [entrando, setEntrando] = useState(false);
  const { definirUsuario } = useAuth();
  const router = useRouter();
  async function entrar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (entrando) return;
    setEntrando(true); setErro("");
    try {
      const usuario = await authRequest<Usuario>("/auth/login", { method: "POST", body: JSON.stringify({ email, senha }) });
      definirUsuario(usuario); setSenha(""); router.replace("/"); router.refresh();
    } catch (error) { setErro(error instanceof Error ? error.message : "Não foi possível entrar."); }
    finally { setEntrando(false); }
  }
  return <main className="artx-leads auth-page"><section className="config-card auth-card"><p className="auth-brand">ART X <span>CRM Agência</span></p><h1>Entrar no CRM</h1><p className="config-muted">Use sua conta para acessar a agência.</p><form onSubmit={entrar}><label>E-mail<input type="email" autoComplete="username" required maxLength={150} value={email} onChange={(e) => setEmail(e.target.value)}/></label><label>Senha<input type="password" autoComplete="current-password" required maxLength={128} value={senha} onChange={(e) => setSenha(e.target.value)}/></label>{erro && <p className="config-message config-error" role="alert">{erro}</p>}<button className="leads-new" disabled={entrando}>{entrando ? "Entrando..." : "Entrar"}</button></form><div className="auth-links"><Link href="/esqueci-senha">Esqueci minha senha</Link><Link href="/verificar-email">Confirmar e-mail</Link></div></section></main>;
}
