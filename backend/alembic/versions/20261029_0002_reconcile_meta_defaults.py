"""Add missing server defaults for monthly metas timestamps.

This revision is non-destructive and targets an already-baselined database.
"""
from alembic import op


revision = "20261029_0002"
down_revision = "20261027_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE public.metas "
        "ALTER COLUMN criado_em SET DEFAULT CURRENT_TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE public.metas "
        "ALTER COLUMN atualizado_em SET DEFAULT CURRENT_TIMESTAMP"
    )


def downgrade():
    raise RuntimeError(
        "Downgrade bloqueado: remocao de defaults exige plano especifico e autorizacao."
    )
