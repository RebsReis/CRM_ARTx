/** Formata a data de calendário da API sem deslocá-la por fuso horário. */
export function formatarData(valor: string | null | undefined, vazio = "Não informado") {
  const partes = valor?.match(/^(\d{4})-(\d{2})-(\d{2})(?:$|T| )/);
  if (!partes) return vazio;
  const [, ano, mes, dia] = partes;
  const a = Number(ano), m = Number(mes), d = Number(dia);
  const bissexto = a % 4 === 0 && (a % 100 !== 0 || a % 400 === 0);
  const dias = [31, bissexto ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (m < 1 || m > 12 || d < 1 || d > dias[m - 1]) return vazio;
  return `${dia}/${mes}/${ano}`;
}
