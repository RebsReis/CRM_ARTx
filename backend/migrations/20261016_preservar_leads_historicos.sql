-- Executar em uma transacao antes de iniciar a nova versao do backend.
-- Exclusao logica preserva FKs, historicos, reunioes e a primeira prospeccao.
-- Idempotente e aditiva: nenhuma linha existente e removida ou recalculada.
ALTER TABLE leads ADD COLUMN IF NOT EXISTS arquivado_em timestamp without time zone;
