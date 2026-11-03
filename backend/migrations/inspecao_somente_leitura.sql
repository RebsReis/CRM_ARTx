-- PREPARADO, NAO EXECUTADO. Exige autorizacao antes de consultar qualquer banco.
-- Somente catalogos: nao consulta linhas comerciais, usuarios, hashes ou tokens.
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL lock_timeout = '3s';
SET LOCAL statement_timeout = '15s';

SELECT current_setting('server_version_num') AS server_version_num,
       current_setting('TimeZone') AS timezone;

SELECT table_name, ordinal_position, column_name, data_type, udt_name,
       character_maximum_length, numeric_precision, numeric_scale,
       is_nullable, column_default, is_identity, identity_generation
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position;

SELECT c.relname AS tabela, con.conname, con.contype, con.convalidated,
       pg_get_constraintdef(con.oid, true) AS definicao
FROM pg_constraint con
JOIN pg_class c ON c.oid = con.conrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
ORDER BY c.relname, con.conname;

SELECT tablename, indexname, indexdef
FROM pg_indexes WHERE schemaname = 'public'
ORDER BY tablename, indexname;

SELECT c.relname AS tabela, t.tgname, t.tgenabled,
       pg_get_triggerdef(t.oid, true) AS definicao
FROM pg_trigger t
JOIN pg_class c ON c.oid = t.tgrelid
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND NOT t.tgisinternal
ORDER BY c.relname, t.tgname;

SELECT DISTINCT pn.nspname AS esquema, p.proname,
       pg_get_function_identity_arguments(p.oid) AS argumentos,
       pg_get_functiondef(p.oid) AS definicao
FROM pg_proc p
JOIN pg_namespace pn ON pn.oid = p.pronamespace
WHERE (pn.nspname = 'public' AND p.proname = 'registrar_historico_lead')
   OR p.oid IN (
       SELECT t.tgfoid FROM pg_trigger t
       JOIN pg_class c ON c.oid = t.tgrelid
       JOIN pg_namespace n ON n.oid = c.relnamespace
       WHERE n.nspname = 'public' AND NOT t.tgisinternal
   )
ORDER BY esquema, proname, argumentos;

SELECT schemaname, sequencename, data_type, start_value, min_value,
       max_value, increment_by, cycle, cache_size
FROM pg_sequences WHERE schemaname = 'public'
ORDER BY sequencename;

SELECT extname, extversion FROM pg_extension ORDER BY extname;
SELECT to_regclass('public.alembic_version') IS NOT NULL AS alembic_instalado;
ROLLBACK;
