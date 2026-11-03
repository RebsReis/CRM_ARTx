type ProjetoPrazo = { id: number; status: string; prazo: string | null };

export function projetoConcluido(projeto: Pick<ProjetoPrazo, "status">) {
  return ["FINALIZADA", "CONCLUIDO"].includes(projeto.status);
}

export function situacaoPrazo(projeto: Pick<ProjetoPrazo, "status" | "prazo">, hoje: string) {
  if (!hoje || !projeto.prazo || projetoConcluido(projeto)) return "normal";
  const prazo = projeto.prazo.slice(0, 10);
  return prazo < hoje ? "vencido" : prazo === hoje ? "hoje" : "normal";
}

export function selecionarProjetos<T extends ProjetoPrazo>(projetos: T[], hoje: string, filtroPrazo: string) {
  return projetos.filter((projeto) => {
    const situacao = situacaoPrazo(projeto, hoje);
    return filtroPrazo === "vencidos" ? situacao === "vencido"
      : filtroPrazo === "hoje" ? situacao === "hoje"
      : filtroPrazo === "urgentes" ? situacao !== "normal" : true;
  }).sort((a, b) => {
    const urgenteA = situacaoPrazo(a, hoje) !== "normal";
    const urgenteB = situacaoPrazo(b, hoje) !== "normal";
    return Number(urgenteB) - Number(urgenteA)
      || (a.prazo?.slice(0, 10) ?? "9999").localeCompare(b.prazo?.slice(0, 10) ?? "9999")
      || a.id - b.id;
  });
}
