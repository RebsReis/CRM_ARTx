"""Create contract-value history and import a deployment snapshot."""
from alembic import op


revision = "20261029_0003"
down_revision = "20261029_0002"
branch_labels = None
depends_on = None


def upgrade():
    # Requires CREATE EXTENSION privilege on the target database.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("""
        CREATE TABLE public.cliente_valores_mensais (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            cliente_id BIGINT NOT NULL REFERENCES public.clientes(id) ON DELETE CASCADE,
            valor_mensal NUMERIC(12, 2) NOT NULL,
            vigencia_inicio DATE NOT NULL,
            vigencia_fim DATE NULL,
            origem VARCHAR(30) NOT NULL,
            criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT cliente_valores_mensais_valor_check CHECK (valor_mensal >= 0),
            CONSTRAINT cliente_valores_mensais_datas_check CHECK (vigencia_fim IS NULL OR vigencia_fim > vigencia_inicio),
            CONSTRAINT cliente_valores_mensais_origem_check CHECK (origem IN ('CADASTRO', 'REAJUSTE', 'MIGRACAO_SNAPSHOT'))
        )
    """)
    op.execute("""
        ALTER TABLE public.cliente_valores_mensais
        ADD CONSTRAINT cliente_valores_mensais_sem_sobreposicao
        EXCLUDE USING gist (
            cliente_id WITH =,
            daterange(vigencia_inicio, COALESCE(vigencia_fim, 'infinity'::date), '[)') WITH &&
        )
    """)
    op.execute("CREATE INDEX ix_cliente_valores_mensais_cliente_inicio ON public.cliente_valores_mensais (cliente_id, vigencia_inicio)")
    op.execute("""
        INSERT INTO public.cliente_valores_mensais
            (cliente_id, valor_mensal, vigencia_inicio, vigencia_fim, origem)
        SELECT id, valor_mensal, CURRENT_DATE, NULL,
               'MIGRACAO_SNAPSHOT'
        FROM public.clientes
    """)


def downgrade():
    raise RuntimeError("Downgrade bloqueado: histórico financeiro exige restauração autorizada.")
