"use client";

import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { authRequest, useAuth, type Usuario } from "../../components/AuthShell";
import PasswordInput from "../../components/PasswordInput";
import ThemeSettings from "../../components/ThemeSettings";
import "./configuracoes.css";

function Modal({ titulo, children, fechar, ocupado }: { titulo: string; children: ReactNode; fechar: () => void; ocupado: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current; dialog?.showModal(); return () => dialog?.close(); }, []);
  return <dialog ref={ref} className="config-modal" aria-labelledby="config-modal-title" onCancel={(event) => { event.preventDefault(); if (!ocupado) fechar(); }} onClick={(event) => { if (event.target === event.currentTarget && !ocupado) fechar(); }}><div className="config-section-title"><h2 id="config-modal-title">{titulo}</h2><button type="button" aria-label="Fechar janela" disabled={ocupado} onClick={fechar}>×</button></div>{children}</dialog>;
}
type Edicao = { modo: "criar" } | { modo: "editar" | "senha"; alvo: Usuario };

function FormUsuario({ edicao, fechar, concluido }: { edicao: Edicao; fechar: () => void; concluido: () => Promise<void> }) {
  const alvo = "alvo" in edicao ? edicao.alvo : null;
  const [nome, setNome] = useState(alvo?.nome ?? "");
  const [email, setEmail] = useState(alvo?.email ?? "");
  const [tipo, setTipo] = useState<"ADMIN" | "USUARIO">(alvo?.tipo ?? "USUARIO");
  const [ativo, setAtivo] = useState(alvo?.ativo ?? true);
  const [senha, setSenha] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const titulo = edicao.modo === "criar" ? "Adicionar usuário" : edicao.modo === "senha" ? "Redefinir senha" : "Editar usuário";
  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (salvando) return;
    if (edicao.modo === "senha" && !window.confirm(`Redefinir a senha de ${alvo?.nome}? As sessões dessa conta serão encerradas.`)) return;
    if (edicao.modo === "editar" && alvo?.ativo && !ativo && !window.confirm(`Desativar a conta de ${alvo.nome} e encerrar suas sessões?`)) return;
    setSalvando(true); setErro("");
    try {
      if (edicao.modo === "senha") await authRequest(`/usuarios/${alvo!.id}/senha`, { method: "POST", body: JSON.stringify({ nova_senha: senha }) });
      else if (edicao.modo === "criar") await authRequest("/usuarios", { method: "POST", body: JSON.stringify({ nome, email, tipo, senha }) });
      else await authRequest(`/usuarios/${alvo!.id}`, { method: "PUT", body: JSON.stringify({ nome, email, tipo, ativo }) });
      setSenha(""); await concluido(); fechar();
    } catch (error) { setErro(error instanceof Error ? error.message : "Não foi possível salvar."); }
    finally { setSalvando(false); }
  }
  return <Modal titulo={titulo} fechar={fechar} ocupado={salvando}><form onSubmit={salvar}><fieldset disabled={salvando}>
    {edicao.modo !== "senha" && <><label>Nome<input required maxLength={150} value={nome} onChange={(e) => setNome(e.target.value)}/></label><label>E-mail<input type="email" required maxLength={150} value={email} onChange={(e) => setEmail(e.target.value)}/></label><label>Perfil<select value={tipo} onChange={(e) => setTipo(e.target.value as "ADMIN" | "USUARIO")} disabled={alvo?.tipo === "ADMIN"}><option value="USUARIO">Usuário</option><option value="ADMIN" disabled={alvo?.tipo !== "ADMIN"}>Administrador principal (único)</option></select></label></>}
    {edicao.modo !== "editar" && <label>{edicao.modo === "criar" ? "Senha inicial" : `Nova senha de ${alvo?.nome}`}<PasswordInput autoComplete="new-password" required minLength={8} maxLength={128} value={senha} onChange={(e) => setSenha(e.target.value)}/><small>Entre 8 e 128 caracteres. Use uma senha exclusiva.</small></label>}
    {edicao.modo === "editar" && <label>Status<select value={ativo ? "ATIVO" : "INATIVO"} disabled={alvo?.tipo === "ADMIN"} onChange={(e) => setAtivo(e.target.value === "ATIVO")}><option value="ATIVO">Ativo</option><option value="INATIVO">Inativo</option></select></label>}
    </fieldset>{erro && <p className="config-message config-error" role="alert">{erro}</p>}<div className="config-actions"><button type="button" className="config-secondary" disabled={salvando} onClick={fechar}>Cancelar</button><button className="leads-new" disabled={salvando}>{salvando ? "Salvando..." : "Salvar"}</button></div></form></Modal>;
}

function Usuarios({ usuario }: { usuario: Usuario }) {
  const [usuarios, setUsuarios] = useState<Usuario[]>([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  const [edicao, setEdicao] = useState<Edicao | null>(null);
  const [aprovando, setAprovando] = useState<number | null>(null);
  const { definirUsuario } = useAuth();
  const carregar = useCallback(async (signal?: AbortSignal) => {
    try { const dados = await authRequest<Usuario[]>("/usuarios", { signal }); if (!signal?.aborted) { setUsuarios(dados); setErro(""); } }
    catch (error) { if (!signal?.aborted) setErro(error instanceof Error ? error.message : "Não foi possível carregar usuários."); }
    finally { if (!signal?.aborted) setCarregando(false); }
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const inicio = window.setTimeout(() => void carregar(controller.signal), 0);
    return () => { window.clearTimeout(inicio); controller.abort(); };
  }, [carregar]);
  async function concluido() {
    setSucesso("Operação concluída com sucesso.");
    await carregar();
    const atual = await authRequest<Usuario>("/auth/me"); definirUsuario(atual);
  }
  async function avaliar(alvo: Usuario, status_acesso: "APROVADO" | "RECUSADO") {
    if (aprovando !== null || !window.confirm(`${status_acesso === "APROVADO" ? "Aprovar" : "Recusar"} o acesso de ${alvo.nome}?`)) return;
    setAprovando(alvo.id); setErro("");
    try { await authRequest(`/usuarios/${alvo.id}/aprovacao`, { method: "POST", body: JSON.stringify({ status_acesso }) }); await concluido(); }
    catch (error) { setErro(error instanceof Error ? error.message : "Não foi possível avaliar o acesso."); }
    finally { setAprovando(null); }
  }
  return <section className="config-card"><div className="config-section-title"><div><h2>Usuários</h2><p className="config-muted">Gerencie os acessos à agência.</p></div><button className="leads-new" onClick={() => { setSucesso(""); setEdicao({ modo: "criar" }); }}>+ Adicionar usuário</button></div>
    {carregando && <p role="status">Carregando usuários...</p>}{erro && <p className="config-message config-error" role="alert">{erro}<button className="config-secondary" onClick={() => void carregar()}>Tentar novamente</button></p>}{sucesso && <p className="config-message config-success" role="status">{sucesso}</p>}
    <div className="config-table-wrap"><table><caption className="sr-only">Contas e permissões de acesso ao CRM</caption><thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Status</th><th>Acesso</th><th>Ações</th></tr></thead><tbody>{usuarios.map((item) => <tr key={item.id}><td>{item.nome}{item.id === usuario.id && <small>Você</small>}</td><td>{item.email}</td><td>{item.tipo === "ADMIN" ? "Administrador" : "Usuário"}</td><td><span className={`config-badge ${item.ativo ? "config-active" : ""}`}>{item.ativo ? "Ativo" : "Inativo"}</span></td><td>{item.status_acesso}<small>{item.email_verificado ? "E-mail confirmado" : "E-mail pendente"}</small></td><td><div className="config-row-actions">{item.tipo !== "ADMIN" && <>{item.status_acesso !== "APROVADO" && <button className="config-secondary" disabled={aprovando !== null} onClick={() => void avaliar(item, "APROVADO")}>Aprovar</button>}{item.status_acesso !== "RECUSADO" && <button className="config-secondary" disabled={aprovando !== null} onClick={() => void avaliar(item, "RECUSADO")}>Recusar</button>}</>}<button className="config-secondary" onClick={() => setEdicao({ modo: "editar", alvo: item })}>Editar</button>{item.id !== usuario.id && <button className="config-secondary" onClick={() => setEdicao({ modo: "senha", alvo: item })}>Redefinir senha</button>}</div></td></tr>)}</tbody></table></div>
    <p className="config-muted">O administrador principal não pode ser desativado ou perder seu perfil.</p>
    {edicao && <FormUsuario edicao={edicao} fechar={() => setEdicao(null)} concluido={concluido}/>}
  </section>;
}

function MinhaConta({ usuario }: { usuario: Usuario }) {
  const { definirUsuario } = useAuth();
  const [nome, setNome] = useState(usuario.nome);
  const [email, setEmail] = useState(usuario.email);
  const [senhaAtual, setSenhaAtual] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");
  async function salvar(event: FormEvent<HTMLFormElement>, senha: boolean) {
    event.preventDefault(); if (salvando) return;
    setErro(""); setSucesso("");
    if (senha && novaSenha !== confirmacao) { setErro("A confirmação da senha não confere."); return; }
    if (senha && !window.confirm("Alterar sua senha? Você precisará entrar novamente em todos os dispositivos.")) return;
    setSalvando(true);
    try {
      if (senha) {
        await authRequest("/auth/senha", { method: "POST", body: JSON.stringify({ senha_atual: senhaAtual, nova_senha: novaSenha, confirmacao }) });
        setSenhaAtual(""); setNovaSenha(""); setConfirmacao(""); definirUsuario(null);
      } else {
        const atual = await authRequest<Usuario>("/auth/me", { method: "PATCH", body: JSON.stringify({ nome, email, ...(email !== usuario.email ? { senha_atual: senhaAtual } : {}) }) });
        definirUsuario(atual); setNome(atual.nome); setEmail(atual.email); setSenhaAtual(""); setSucesso(email !== atual.email ? "Confirmação enviada ao novo e-mail. O endereço atual permanece até a confirmação." : "Dados pessoais atualizados.");
      }
    } catch (error) { setErro(error instanceof Error ? error.message : "Não foi possível salvar."); }
    finally { setSalvando(false); }
  }
  return <section className="config-card"><div className="config-section-title"><div><h2>Minha conta</h2><p className="config-muted">Seus dados e a segurança do seu acesso.</p></div><span className="config-badge">{usuario.tipo === "ADMIN" ? "Administrador" : "Usuário"}</span></div>
    {erro && <p className="config-message config-error" role="alert">{erro}</p>}{sucesso && <p className="config-message config-success" role="status">{sucesso}</p>}
    <div className="config-account-grid"><form onSubmit={(e) => void salvar(e, false)}><h3>Dados pessoais</h3><fieldset disabled={salvando}><label>Nome<input required maxLength={150} value={nome} onChange={(e) => setNome(e.target.value)}/></label><label>E-mail<input type="email" required maxLength={150} value={email} onChange={(e) => setEmail(e.target.value)}/></label>{email !== usuario.email && <label>Senha atual para alterar o e-mail<input type="password" required autoComplete="current-password" value={senhaAtual} onChange={(event) => setSenhaAtual(event.target.value)}/></label>}</fieldset><button className="leads-new" disabled={salvando}>Salvar meus dados</button></form>
    <form onSubmit={(e) => void salvar(e, true)}><h3>Alterar minha senha</h3><fieldset disabled={salvando}><label>Senha atual<input type="password" autoComplete="current-password" required maxLength={128} value={senhaAtual} onChange={(e) => setSenhaAtual(e.target.value)}/></label><label>Nova senha<PasswordInput autoComplete="new-password" required minLength={8} maxLength={128} value={novaSenha} onChange={(e) => setNovaSenha(e.target.value)}/></label><label>Confirme a nova senha<PasswordInput autoComplete="new-password" required minLength={8} maxLength={128} value={confirmacao} onChange={(e) => setConfirmacao(e.target.value)}/></label></fieldset><button className="config-secondary" disabled={salvando}>Alterar senha</button></form></div>
  </section>;
}

export default function ConfiguracoesPage() {
  const { usuario } = useAuth();
  if (!usuario) return null;
  return <main className="artx-leads artx-configuracoes"><div className="leads-topbar"><span>Preferências da agência</span><span>ART X <span className="leads-topbar-caption">CRM Agência</span></span></div><div className="leads-content-heading"><div><h1>Configurações</h1><p>Gerencie os acessos e mantenha sua conta atualizada.</p></div></div>
    {usuario.tipo === "ADMIN" ? <Usuarios usuario={usuario}/> : <section className="config-card"><h2>Usuários</h2><p className="config-muted">O gerenciamento de contas é exclusivo do administrador.</p></section>}
    <section className="config-card"><h2>Perfis e permissões</h2><p className="config-muted">Cada conta acessa as funcionalidades de acordo com seu perfil.</p><div className="config-table-wrap"><table><caption className="sr-only">Permissões por perfil</caption><thead><tr><th>Funcionalidade</th><th>Administrador</th><th>Usuário</th></tr></thead><tbody><tr><td>Dashboard, Leads, Clientes, Projetos e Metas</td><td>Permitido</td><td>Permitido</td></tr><tr><td>Cadastrar, editar e desativar usuários</td><td>Permitido</td><td>Não permitido</td></tr><tr><td>Redefinir senhas de outras contas</td><td>Permitido</td><td>Não permitido</td></tr><tr><td>Atualizar dados e senha da própria conta</td><td>Permitido</td><td>Permitido</td></tr></tbody></table></div></section>
    <ThemeSettings/>
    <MinhaConta key={usuario.id} usuario={usuario}/>
  </main>;
}

