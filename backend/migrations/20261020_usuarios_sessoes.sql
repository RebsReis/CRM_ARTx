-- Reutiliza usuarios. Pre-condicoes falham sem modificar usuarios existentes.
DO $$
BEGIN
    IF (SELECT count(*) FROM usuarios WHERE tipo = 'ADMIN') > 1 THEN
        RAISE EXCEPTION 'Mais de um administrador existente: conciliar manualmente antes da migracao.';
    END IF;
    IF EXISTS (SELECT 1 FROM usuarios WHERE tipo = 'ADMIN' AND NOT ativo) THEN
        RAISE EXCEPTION 'Administrador existente inativo: conciliar manualmente antes da migracao.';
    END IF;
    IF EXISTS (SELECT lower(email) FROM usuarios GROUP BY lower(email) HAVING count(*) > 1) THEN
        RAISE EXCEPTION 'Emails duplicados sem distinguir maiusculas: conciliar antes da migracao.';
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS usuarios_email_normalizado ON usuarios (lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS usuarios_um_admin ON usuarios (tipo) WHERE tipo = 'ADMIN';
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'usuarios'::regclass AND conname = 'usuarios_admin_ativo') THEN
        ALTER TABLE usuarios ADD CONSTRAINT usuarios_admin_ativo CHECK (tipo <> 'ADMIN' OR ativo);
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS sessoes_usuario (
    token_hash varchar(64) PRIMARY KEY,
    usuario_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    expira_em timestamptz NOT NULL,
    criado_em timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_sessoes_usuario_usuario_id ON sessoes_usuario (usuario_id);
CREATE INDEX IF NOT EXISTS ix_sessoes_usuario_expira_em ON sessoes_usuario (expira_em);
CREATE TABLE IF NOT EXISTS tentativas_login (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    chave varchar(64) NOT NULL,
    criado_em timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_tentativas_login_chave ON tentativas_login (chave);
