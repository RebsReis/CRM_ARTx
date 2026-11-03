"use client";

import { useTheme } from "./ThemeProvider";

export default function ThemeSettings() {
  const { tema, mudarTema } = useTheme();
  return <section className="config-card">
    <h2>Aparência</h2>
    <p className="config-muted">Escolha o tema do CRM. Sua preferência fica salva neste navegador.</p>
    <label className="theme-select">Tema
      <select value={tema} onChange={(event) => mudarTema(event.target.value === "claro" ? "claro" : "escuro")}>
        <option value="escuro">Escuro</option>
        <option value="claro">Claro</option>
      </select>
    </label>
    <p className="config-muted" role="status">Tema {tema} ativado.</p>
  </section>;
}
