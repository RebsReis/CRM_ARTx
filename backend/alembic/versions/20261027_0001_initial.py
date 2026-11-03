"""Baseline candidata para banco NOVO, bloqueada ate reconciliacao do esquema real."""
from alembic import op
from schema_guard import bootstrap_statements

revision = "20261027_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    schema_sql, trigger_sql = bootstrap_statements()
    op.execute(schema_sql)
    op.execute(trigger_sql)


def downgrade():
    raise RuntimeError("Baseline sem downgrade destrutivo; exige restauracao autorizada.")
