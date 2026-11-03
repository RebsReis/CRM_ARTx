"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import "../app/theme.css";

type Tema = "claro" | "escuro";
const chave = "artx-tema";
const ThemeContext = createContext<{ tema: Tema; mudarTema: (tema: Tema) => void } | null>(null);

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("Tema indisponível.");
  return context;
}

export default function ThemeProvider({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>("escuro");
  function aplicar(valor: Tema) {
    document.documentElement.dataset.tema = valor;
    setTema(valor);
  }
  useEffect(() => {
    const inicio = window.setTimeout(() => {
      try { aplicar(localStorage.getItem(chave) === "claro" ? "claro" : "escuro"); }
      catch { aplicar("escuro"); }
    }, 0);
    const sincronizar = (event: StorageEvent) => {
      if (event.key === chave || event.key === null) aplicar(event.newValue === "claro" ? "claro" : "escuro");
    };
    window.addEventListener("storage", sincronizar);
    return () => { window.clearTimeout(inicio); window.removeEventListener("storage", sincronizar); };
  }, []);
  function mudarTema(valor: Tema) {
    aplicar(valor);
    try { localStorage.setItem(chave, valor); } catch { /* O tema permanece ativo mesmo com armazenamento bloqueado. */ }
  }
  return <ThemeContext.Provider value={{ tema, mudarTema }}>{children}</ThemeContext.Provider>;
}
