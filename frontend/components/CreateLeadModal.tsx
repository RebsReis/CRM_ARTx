"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { authRequest } from "./AuthShell";

export type CreatedLead = {
  id: number; nome_empresa: string; nicho: string | null; telefone: string | null;
  email: string | null; fase: string; observacao: string | null;
};
const vazio = { nome_empresa: "", nicho: "", telefone: "", email: "", fase: "PROSPECTAR", observacao: "" };

export default function CreateLeadModal({ fechar, aoCriar }: { fechar: () => void; aoCriar?: (lead: CreatedLead) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const enviando = useRef(false);
  const [dados, setDados] = useState(vazio);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState("");
  useEffect(() => { const modal = dialog.current; modal?.showModal(); return () => modal?.close(); }, []);
  async function salvar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (enviando.current) return;
    if (!dados.nome_empresa.trim()) { setErro("Informe o nome da empresa."); return; }
    enviando.current = true; setSalvando(true); setErro("");
    try {
      const lead = await authRequest<CreatedLead>("/leads", { method: "POST", body: JSON.stringify({ ...dados, nome_empresa: dados.nome_empresa.trim() }) });
      aoCriar?.(lead); fechar();
    } catch (error) { setErro(error instanceof Error ? error.message : "Não foi possível criar o lead."); }
    finally { enviando.current = false; setSalvando(false); }
  }
  return <dialog ref={dialog} className="config-modal" aria-labelledby="create-lead-title" onCancel={(event) => { event.preventDefault(); if (!salvando) fechar(); }}>
    <div className="config-section-title"><h2 id="create-lead-title">Novo lead</h2><button type="button" aria-label="Fechar formulário" disabled={salvando} onClick={fechar}>×</button></div>
    <p className="config-muted">Cadastre uma nova oportunidade comercial para a ART X.</p>
    <form onSubmit={salvar}><fieldset disabled={salvando}>
      <label>Nome da empresa *<input autoFocus required maxLength={150} value={dados.nome_empresa} onChange={(e) => setDados({ ...dados, nome_empresa: e.target.value })} placeholder="Ex.: Adidas"/></label>
      <label>Nicho<input maxLength={100} value={dados.nicho} onChange={(e) => setDados({ ...dados, nicho: e.target.value })}/></label>
      <label>Telefone<input type="tel" maxLength={30} value={dados.telefone} onChange={(e) => setDados({ ...dados, telefone: e.target.value })}/></label>
      <label>E-mail<input type="email" maxLength={150} value={dados.email} onChange={(e) => setDados({ ...dados, email: e.target.value })}/></label>
      <label>Etapa comercial<select value={dados.fase} onChange={(e) => setDados({ ...dados, fase: e.target.value })}>
        <option value="PROSPECTAR">Prospectar</option><option value="FOLLOW_UP">Follow-up</option><option value="REUNIAO_MARCADA">Reunião marcada</option><option value="REMARKETING_FUTURO">Remarketing futuro</option>
      </select></label>
      <label>Observações<textarea className="create-lead-notes" rows={3} value={dados.observacao} onChange={(e) => setDados({ ...dados, observacao: e.target.value })}/></label>
    </fieldset>{erro && <p className="config-message config-error" role="alert">{erro}</p>}
      <div className="config-actions"><button type="button" className="config-secondary" disabled={salvando} onClick={fechar}>Cancelar</button><button type="submit" className="leads-new" disabled={salvando}>{salvando ? "Salvando..." : "Salvar lead"}</button></div>
    </form>
  </dialog>;
}
