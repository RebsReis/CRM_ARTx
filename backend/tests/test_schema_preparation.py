"""Verificacao estatica de SQL, inventario e travas. Nao aplica revisoes."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.dialects import postgresql
from alembic.config import Config
from alembic.script import ScriptDirectory
from models import Base
import auth_models
import psycopg
from schema_guard import ASSETS, bootstrap_statements, validate_operation, BASELINE_REVISION


class SchemaPreparationTest(unittest.TestCase):
    def setUp(self):
        a = patch.object(Engine, "connect", side_effect=AssertionError("Conexao proibida"))
        b = patch.object(psycopg, "connect", side_effect=AssertionError("Conexao proibida"))
        a.start(); b.start()
        self.addCleanup(a.stop); self.addCleanup(b.stop)

    def test_metadata_compila_sem_banco(self):
        dialect = postgresql.dialect()
        for table in Base.metadata.sorted_tables:
            self.assertIn("CREATE TABLE", str(CreateTable(table).compile(dialect=dialect)))
            for index in table.indexes:
                self.assertIn("INDEX", str(CreateIndex(index).compile(dialect=dialect)))

    def test_inventario_e_snapshot_completos_para_o_conhecido(self):
        inventory = json.loads((BACKEND / "migrations/inventario_esquema.json").read_text(encoding="utf-8"))
        self.assertEqual(len(inventory["tables"]), 13)
        self.assertEqual(sum(len(t["columns"]) for t in inventory["tables"].values()), 92)
        ddl = (ASSETS / "initial_schema.sql").read_text(encoding="utf-8")
        for name in inventory["tables"]:
            self.assertIn("CREATE TABLE public." + name, ddl)
        self.assertIn("usuarios_email_normalizado", ddl)
        self.assertIn("tokens_email_finalidade_check", ddl)
        self.assertNotIn("CREATE FUNCTION", ddl)
        self.assertNotIn("CREATE TRIGGER", ddl)

    def test_hashes_dos_artefatos_e_sqls_historicos(self):
        manifest = json.loads((ASSETS / "manifest.json").read_text())
        self.assertEqual(hashlib.sha256((ASSETS / "initial_schema.sql").read_bytes()).hexdigest(),
                         manifest["sha256"]["initial_schema.sql"])
        for path, digest in manifest["historical_sql_sha256"].items():
            self.assertEqual(hashlib.sha256((BACKEND / path).read_bytes()).hexdigest(), digest)

    def test_baseline_incompleta_falha_antes_de_qualquer_ddl(self):
        manifest = json.loads((ASSETS / "manifest.json").read_text())
        if manifest["status"] != "confirmed":
            with self.assertRaisesRegex(RuntimeError, "Baseline bloqueada"):
                bootstrap_statements()
        else:
            self.assertEqual(len(bootstrap_statements()), 2)

    def test_operacoes_sem_autorizacao_e_downgrade_bloqueados(self):
        for command in ("upgrade", "stamp", "current", "check", "revision"):
            with self.assertRaises(RuntimeError):
                validate_operation(command, {})
        with self.assertRaises(RuntimeError):
            validate_operation("downgrade", {"allow_database_access": "yes", "mode": "existing", "schema_reviewed": "yes"})
        with self.assertRaises(RuntimeError):
            validate_operation("stamp", {"allow_database_access": "yes", "mode": "existing"})

    def test_historico_alembic_e_estatico(self):
        scripts = ScriptDirectory.from_config(Config(str(BACKEND / "alembic.ini")))
        # Cadeia linear: baseline -> 0002 -> 0003 -> 0004, sem ramificacoes.
        cadeia = [r.revision for r in scripts.walk_revisions()][::-1]
        self.assertEqual(cadeia, [BASELINE_REVISION, "20261029_0002", "20261029_0003", "20261103_0004"])
        self.assertEqual(scripts.get_heads(), ["20261103_0004"])
        self.assertIsNone(scripts.get_revision(BASELINE_REVISION).down_revision)

    def test_inspecao_preparada_e_somente_leitura(self):
        sql = (BACKEND / "migrations/inspecao_somente_leitura.sql").read_text()
        self.assertIn("READ ONLY", sql)
        self.assertTrue(sql.strip().endswith("ROLLBACK;"))
        self.assertNotIn("SELECT * FROM usuarios", sql)
