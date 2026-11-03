import json
from pathlib import Path
import unittest


ROOT = Path(__file__).parents[1]
SQL = (ROOT / "alembic/sql/initial_schema.sql").read_text(encoding="utf-8")
TRIGGERS = (ROOT / "alembic/sql/history_triggers.sql").read_text(encoding="utf-8")
INV = json.loads((ROOT / "migrations/inventario_esquema.json").read_text(encoding="utf-8"))


class BaselineOfflineTests(unittest.TestCase):
    def test_inventory_object_counts(self):
        self.assertEqual(len(INV["tables"]), 13)
        self.assertEqual(sum(len(t["columns"]) for t in INV["tables"].values()), 92)

    def test_reconciled_objects_are_in_ddl(self):
        for token in ("uq_meta_mes", "fk_historico_lead", "leads_fase_check", "metas_mes_check",
                      "ON DELETE CASCADE", "ON DELETE SET NULL", "GENERATED ALWAYS"):
            self.assertIn(token, SQL)
        for token in ("registrar_historico_lead", "trigger_historico_lead", "trigger_atualizar_clientes",
                      "trigger_atualizar_metas", "trigger_atualizar_projetos", "trigger_atualizar_usuarios"):
            self.assertIn(token, TRIGGERS)

    def test_baseline_is_not_connected(self):
        self.assertNotIn("create_engine(", SQL)
        self.assertNotIn("psycopg", SQL)


if __name__ == "__main__":
    unittest.main()
