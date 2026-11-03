"use client";

import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import { authRequest } from "./AuthShell";
import PasswordInput from "./PasswordInput";

type Mode = "recuperacao" | "redefinir" | "verificar";
const titles = { recuperacao: "Esqueci minha senha", redefinir: "Definir nova senha", verificar: "Confirmar e-mail" };

export default function PublicAuthForm({ mode }: { mode: Mode }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [token, setToken] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [enviando, setEnviando] = useState(false);
  useEffect(() => {
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token");
    const inicio = window.setTimeout(() => { if (value) { setToken(value); window.history.replaceState(null, "", window.location.pathname); } }, 0);
    return () => window.clearTimeout(inicio);
  }, []);
  async function enviar(event: FormEvent<HTMLFormElement>, reenviar = false) {
    event.preventDefault(); if (enviando) return;
    setErro(""); setMensagem("");
    if ((mode === "redefinir") && senha !== confirmacao) { setErro("A confirmação da senha não confere."); return; }
    setEnviando(true);
    try {
      const route = reenviar ? "/auth/reenviar-verificacao" : { recuperacao: "/auth/recuperacao", redefinir: "/auth/redefinir", verificar: "/auth/verificar" }[mode];
      const body = reenviar || mode === "recuperacao" ? { email } : mode === "redefinir" ? { token, nova_senha: senha, confirmacao } : { token };
      const result = await authRequest<{ mensagem: string }>(route, { method: "POST", body: JSON.stringify(body) });
      setMensagem(result.mensagem); setSenha(""); setConfirmacao("");
      if (mode === "redefinir" || (mode === "verificar" && !reenviar)) setToken("");
    } catch (error) { setErro(error instanceof Error ? error.message : "Não foi possível concluir a solicitação."); }
    finally { setEnviando(false); }
  }
  return <main className="artx-leads auth-page"><section className="config-card auth-card"><p className="auth-brand">ART X <span>CRM Agência</span></p><h1>{titles[mode]}</h1><p className="config-muted">{mode === "recuperacao" ? "Receba um link temporário no seu e-mail." : mode === "verificar" ? "Confirme o endereço antes de acessar o CRM." : "Use uma senha exclusiva de 8 a 128 caracteres."}</p>
    <form onSubmit={(event) => void enviar(event, mode === "verificar" && !token)}><fieldset disabled={enviando}>
      {(mode === "recuperacao" || (mode === "verificar" && !token)) && <label>E-mail<input required type="email" maxLength={150} autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)}/></label>}
      {(mode === "redefinir") && <><label>Senha<PasswordInput required minLength={8} maxLength={128} autoComplete="new-password" value={senha} onChange={(event) => setSenha(event.target.value)}/></label><label>Confirme a senha<PasswordInput required minLength={8} maxLength={128} autoComplete="new-password" value={confirmacao} onChange={(event) => setConfirmacao(event.target.value)}/></label></>}
      {mode === "redefinir" && !token && !mensagem && <p className="config-message">Abra o link enviado ao seu e-mail. Se expirou, solicite outro abaixo.</p>}
      {erro && <p className="config-message config-error" role="alert">{erro}</p>}{mensagem && <p className="config-message config-success" role="status">{mensagem}</p>}
      <button className="leads-new" disabled={enviando || (mode === "redefinir" && !token)}>{enviando ? "Enviando..." : mode === "verificar" ? token ? "Confirmar meu e-mail" : "Reenviar confirmação" : mode === "redefinir" ? "Salvar nova senha" : "Enviar instruções"}</button>
    </fieldset></form>
    <div className="auth-links"><Link href="/login">Voltar para o login</Link><Link href="/esqueci-senha">Solicitar recuperação</Link></div>
  </section></main>;
}
