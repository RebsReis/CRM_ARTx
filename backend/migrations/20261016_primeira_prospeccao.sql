-- Recupera somente datas ausentes a partir da primeira saida real de PROSPECTAR.
-- Idempotente: nao altera registros ja preenchidos nem remove historicos.
UPDATE leads AS lead
SET prospectado_em = primeira.data_prospeccao
FROM (
    SELECT lead_id, MIN(movimentado_em) AS data_prospeccao
    FROM historico_leads
    WHERE fase_anterior = 'PROSPECTAR'
      AND fase_nova IN ('FOLLOW_UP', 'REUNIAO_MARCADA', 'REMARKETING_FUTURO')
    GROUP BY lead_id
) AS primeira
WHERE lead.id = primeira.lead_id
  AND lead.prospectado_em IS NULL;
