"""Add server defaults the models rely on but the baseline omitted.

The baseline DDL left these columns without DEFAULT, while the models (and the
original local database) use server defaults. INSERTs that omit the columns, such
as POST /projetos, failed with NotNullViolation on a database created from the
baseline. Values match the original database. Non-destructive: no data changes.
"""
from alembic import op


revision = "20261103_0004"
down_revision = "20261029_0003"
branch_labels = None
depends_on = None

DEFAULTS = (
    ("projetos", "criado_em", "CURRENT_TIMESTAMP"),
    ("checklist_items", "criado_em", "CURRENT_TIMESTAMP"),
    ("checklist_items", "concluido", "false"),
    ("checklist_items", "ordem", "0"),
    ("reunioes", "criado_em", "CURRENT_TIMESTAMP"),
    ("reunioes", "status", "'AGENDADA'"),
    ("metas", "meta_faturamento", "0"),
)


def upgrade():
    for tabela, coluna, padrao in DEFAULTS:
        op.execute(f"ALTER TABLE public.{tabela} ALTER COLUMN {coluna} SET DEFAULT {padrao}")
    # O modelo e o banco original exigem criado_em; falha (e desfaz tudo) se houver nulos.
    op.execute("ALTER TABLE public.reunioes ALTER COLUMN criado_em SET NOT NULL")


def downgrade():
    raise RuntimeError(
        "Downgrade bloqueado: remocao de defaults exige plano especifico e autorizacao."
    )
