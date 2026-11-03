-- Preserva a aprovacao e verificacao das contas anteriores; cadastros publicos
-- definem explicitamente PENDENTE e email_verificado=false.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS status_acesso varchar(20) NOT NULL DEFAULT 'APROVADO';
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email_verificado boolean NOT NULL DEFAULT true;
ALTER TABLE usuarios ALTER COLUMN senha_hash DROP NOT NULL;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='usuarios'::regclass AND conname='usuarios_status_acesso_check') THEN
        ALTER TABLE usuarios ADD CONSTRAINT usuarios_status_acesso_check CHECK (status_acesso IN ('PENDENTE','APROVADO','RECUSADO'));
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS identidades_google (
    sub varchar(255) PRIMARY KEY,
    usuario_id bigint NOT NULL UNIQUE REFERENCES usuarios(id) ON DELETE CASCADE,
    email_google varchar(150) NOT NULL,
    criado_em timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS tokens_email (
    token_hash varchar(64) PRIMARY KEY,
    usuario_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    finalidade varchar(20) NOT NULL CHECK (finalidade IN ('VERIFICAR','RESET')),
    destino_email varchar(150) NOT NULL,
    expira_em timestamptz NOT NULL,
    usado_em timestamptz
);
CREATE INDEX IF NOT EXISTS ix_tokens_email_usuario_id ON tokens_email (usuario_id);
CREATE TABLE IF NOT EXISTS fluxos_google (
    state_hash varchar(64) PRIMARY KEY,
    browser_hash varchar(64) NOT NULL,
    nonce varchar(64) NOT NULL,
    verifier varchar(128) NOT NULL,
    usuario_id bigint REFERENCES usuarios(id) ON DELETE CASCADE,
    sessao_hash varchar(64),
    expira_em timestamptz NOT NULL
);
