import { Suspense } from "react";
import Dashboard from "./Dashboard";

export default function HomePage() {
  return (
    <Suspense fallback={<main className="artx-leads artx-dashboard"><p className="dashboard-notice" role="status">Carregando indicadores...</p></main>}>
      <Dashboard />
    </Suspense>
  );
}

// A tela aguarda a sessao validada pelo AuthShell antes de renderizar.
export const instant = false;
