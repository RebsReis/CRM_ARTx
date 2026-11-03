-- BASELINE CANDIDATA, NAO EXECUTAR DIRETAMENTE.

-- Derivada dos modelos e dos SQLs versionados; nao e dump do banco local.

-- Faltam as definicoes reais de funcoes/triggers. Aplicacao bloqueada pelo Alembic.

-- Defaults somente Python sao preservados como defaults da aplicacao, nao inventados no servidor.



CREATE TABLE public.historico_leads (
	id BIGINT GENERATED ALWAYS AS IDENTITY, 
	lead_id BIGINT NOT NULL, 
	fase_anterior VARCHAR(30), 
	fase_nova VARCHAR(30) NOT NULL, 
	movimentado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE public.leads (
	id BIGINT GENERATED ALWAYS AS IDENTITY, 
	nome_empresa VARCHAR(150) NOT NULL, 
	nicho VARCHAR(100), 
	telefone VARCHAR(30), 
	email VARCHAR(150), 
	fase VARCHAR(30) NOT NULL, 
	observacao TEXT, 
	criado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	atualizado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	prospectado_em TIMESTAMP WITHOUT TIME ZONE, 
	arquivado_em TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id)
);

CREATE TABLE public.metas (
	id BIGSERIAL NOT NULL, 
	ano INTEGER NOT NULL, 
	mes INTEGER NOT NULL, 
	meta_prospeccoes INTEGER NOT NULL, 
	meta_reunioes INTEGER NOT NULL, 
	meta_faturamento NUMERIC(12, 2) NOT NULL, 
	criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	atualizado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE public.tentativas_login (
	id BIGINT GENERATED ALWAYS AS IDENTITY, 
	chave VARCHAR(64) NOT NULL, 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id)
);

CREATE INDEX ix_tentativas_login_chave ON public.tentativas_login (chave);

CREATE TABLE public.usuarios (
	id BIGINT GENERATED ALWAYS AS IDENTITY, 
	nome VARCHAR(150) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	senha_hash VARCHAR(255), 
	status_acesso VARCHAR(20) DEFAULT 'APROVADO' NOT NULL, 
	email_verificado BOOLEAN DEFAULT true NOT NULL, 
	tipo VARCHAR(20) DEFAULT 'USUARIO' NOT NULL, 
	ativo BOOLEAN DEFAULT true NOT NULL, 
	criado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	atualizado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email), 
	CONSTRAINT usuarios_status_acesso_check CHECK (status_acesso IN ('PENDENTE', 'APROVADO', 'RECUSADO')), 
	CONSTRAINT usuarios_admin_ativo CHECK (tipo <> 'ADMIN' OR ativo), 
	CONSTRAINT usuarios_tipo_check CHECK (tipo IN ('ADMIN', 'USUARIO'))
);

CREATE UNIQUE INDEX usuarios_um_admin ON public.usuarios (tipo) WHERE tipo = 'ADMIN';

CREATE TABLE public.clientes (
	id BIGINT GENERATED ALWAYS AS IDENTITY, 
	lead_id BIGINT, 
	nome_empresa VARCHAR(150) NOT NULL, 
	nicho VARCHAR(100), 
	telefone VARCHAR(30), 
	email VARCHAR(150), 
	valor_mensal NUMERIC(12, 2) NOT NULL, 
	data_inicio DATE DEFAULT CURRENT_DATE NOT NULL, 
	data_encerramento DATE, 
	status VARCHAR(20) DEFAULT 'ATIVO' NOT NULL, 
	criado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	atualizado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (lead_id), 
	FOREIGN KEY(lead_id) REFERENCES public.leads (id) ON DELETE SET NULL
);

CREATE TABLE public.fluxos_google (
	state_hash VARCHAR(64) NOT NULL, 
	browser_hash VARCHAR(64) NOT NULL, 
	nonce VARCHAR(64) NOT NULL, 
	verifier VARCHAR(128) NOT NULL, 
	usuario_id BIGINT, 
	sessao_hash VARCHAR(64), 
	expira_em TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (state_hash), 
	FOREIGN KEY(usuario_id) REFERENCES public.usuarios (id) ON DELETE CASCADE
);

CREATE TABLE public.identidades_google (
	sub VARCHAR(255) NOT NULL, 
	usuario_id BIGINT NOT NULL, 
	email_google VARCHAR(150) NOT NULL, 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (sub), 
	UNIQUE (usuario_id), 
	FOREIGN KEY(usuario_id) REFERENCES public.usuarios (id) ON DELETE CASCADE
);

CREATE TABLE public.reunioes (
	id BIGSERIAL NOT NULL, 
	lead_id BIGINT NOT NULL, 
	data_reuniao TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	observacao TEXT, 
	criado_em TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(lead_id) REFERENCES public.leads (id)
);

CREATE TABLE public.sessoes_usuario (
	token_hash VARCHAR(64) NOT NULL, 
	usuario_id BIGINT NOT NULL, 
	expira_em TIMESTAMP WITH TIME ZONE NOT NULL, 
	criado_em TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(usuario_id) REFERENCES public.usuarios (id) ON DELETE CASCADE
);

CREATE INDEX ix_sessoes_usuario_usuario_id ON public.sessoes_usuario (usuario_id);

CREATE TABLE public.tokens_email (
	token_hash VARCHAR(64) NOT NULL, 
	usuario_id BIGINT NOT NULL, 
	finalidade VARCHAR(20) NOT NULL, 
	destino_email VARCHAR(150) NOT NULL, 
	expira_em TIMESTAMP WITH TIME ZONE NOT NULL, 
	usado_em TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(usuario_id) REFERENCES public.usuarios (id) ON DELETE CASCADE
);

CREATE INDEX ix_tokens_email_usuario_id ON public.tokens_email (usuario_id);

CREATE TABLE public.projetos (
	id BIGINT GENERATED ALWAYS AS IDENTITY, 
	cliente_id BIGINT NOT NULL, 
	nome_projeto VARCHAR(200) NOT NULL, 
	prazo DATE, 
	prioridade VARCHAR(20) DEFAULT 'MEDIA' NOT NULL, 
	status VARCHAR(30) DEFAULT 'PENDENTE' NOT NULL, 
	observacao TEXT, 
	criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	atualizado_em TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(cliente_id) REFERENCES public.clientes (id)
);

CREATE TABLE public.checklist_items (
	id BIGSERIAL NOT NULL, 
	projeto_id BIGINT NOT NULL, 
	descricao VARCHAR(255) NOT NULL, 
	concluido BOOLEAN NOT NULL, 
	ordem INTEGER NOT NULL, 
	criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
	concluido_em TIMESTAMP WITHOUT TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES public.projetos (id) ON DELETE CASCADE
);

-- Complementos comprovados nos SQLs historicos, ausentes no metadata:

CREATE UNIQUE INDEX usuarios_email_normalizado ON public.usuarios (lower(email));

CREATE INDEX ix_sessoes_usuario_expira_em ON public.sessoes_usuario (expira_em);

ALTER TABLE public.tokens_email ADD CONSTRAINT tokens_email_finalidade_check CHECK (finalidade IN ('VERIFICAR', 'RESET'));

-- Nao adicionar FK do historico, unicidade mensal ou triggers por suposicao.
-- Reconciled physical constraints recovered from PostgreSQL (29/10/2026).
-- These names/actions are part of the baseline contract for a new empty database.
ALTER TABLE public.leads ADD CONSTRAINT leads_fase_check CHECK (fase IN ('PROSPECTAR','FOLLOW_UP','REUNIAO_MARCADA','REMARKETING_FUTURO'));
ALTER TABLE public.historico_leads ADD CONSTRAINT fk_historico_lead FOREIGN KEY (lead_id) REFERENCES public.leads(id) ON DELETE CASCADE;
ALTER TABLE public.metas ADD CONSTRAINT uq_meta_mes UNIQUE (ano, mes);
ALTER TABLE public.metas ADD CONSTRAINT metas_mes_check CHECK (mes BETWEEN 1 AND 12);
ALTER TABLE public.metas ADD CONSTRAINT metas_meta_prospeccoes_check CHECK (meta_prospeccoes >= 0);
ALTER TABLE public.metas ADD CONSTRAINT metas_meta_reunioes_check CHECK (meta_reunioes >= 0);
ALTER TABLE public.metas ADD CONSTRAINT metas_meta_faturamento_check CHECK (meta_faturamento >= 0);
ALTER TABLE public.clientes ADD CONSTRAINT chk_datas_cliente CHECK (data_encerramento IS NULL OR data_encerramento >= data_inicio);
ALTER TABLE public.clientes ADD CONSTRAINT clientes_status_check CHECK (status IN ('ATIVO','INATIVO'));
ALTER TABLE public.clientes ADD CONSTRAINT clientes_valor_mensal_check CHECK (valor_mensal >= 0);
ALTER TABLE public.projetos ADD CONSTRAINT projetos_prioridade_check CHECK (prioridade IN ('BAIXA','MEDIA','ALTA','URGENTE'));
ALTER TABLE public.projetos ADD CONSTRAINT projetos_status_check CHECK (status IN ('PENDENTE','EM_ANDAMENTO','FINALIZADA'));
ALTER TABLE public.reunioes ADD CONSTRAINT reunioes_status_check CHECK (status IN ('AGENDADA','REALIZADA','CANCELADA'));

