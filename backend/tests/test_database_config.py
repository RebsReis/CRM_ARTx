"""Testes unitarios de configuracao. Nunca conectam a nenhum banco."""
import importlib
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib.parse import quote

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from db_config import build_database_url, build_migration_url, engine_options
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool
import psycopg


class DatabaseConfigTest(unittest.TestCase):
    def setUp(self):
        self.env = {"DB_HOST": "localhost", "DB_PORT": "5432", "DB_NAME": "isolated_not_used",
                    "DB_USER": "unit_test", "DB_PASSWORD": "synthetic@:%/# value"}
        self.connect = patch.object(Engine, "connect", side_effect=AssertionError("Conexao proibida"))
        self.driver = patch.object(psycopg, "connect", side_effect=AssertionError("Conexao proibida"))
        self.connect.start()
        self.driver.start()
        self.addCleanup(self.connect.stop)
        self.addCleanup(self.driver.stop)

    def test_db_parts_preservam_caracteres_especiais(self):
        url = build_database_url(self.env)
        self.assertEqual(url.password, self.env["DB_PASSWORD"])
        self.assertEqual(url.drivername, "postgresql+psycopg")

    def test_database_url_tem_precedencia_e_normaliza_driver(self):
        secret = self.env["DB_PASSWORD"]
        for scheme in ("postgres", "postgresql", "postgresql+psycopg"):
            url = build_database_url({**self.env, "DATABASE_URL":
                f"{scheme}://unit_test:{quote(secret, safe='')}@example.invalid/newdb"})
            self.assertEqual(url.password, secret)
            self.assertEqual(url.database, "newdb")
            self.assertEqual(url.drivername, "postgresql+psycopg")

    def test_local_nao_recebe_tls_ou_timezone_forcados(self):
        url = build_database_url(self.env)
        self.assertEqual(dict(url.query), {})
        opts = engine_options(url, self.env)
        self.assertTrue(opts["pool_pre_ping"])
        self.assertNotIn("options", opts["connect_args"])

    def test_neon_default_verifica_certificado_e_hostname(self):
        url = build_database_url({"DATABASE_URL": "postgresql://unit_test@ep-test.aws.neon.tech/unit"})
        self.assertEqual(url.query["sslmode"], "verify-full")
        self.assertEqual(url.query["sslrootcert"], "system")
        self.assertEqual(url.query["channel_binding"], "require")

    def test_neon_recusa_tls_desabilitado(self):
        for mode in ("disable", "allow", "prefer"):
            with self.assertRaises(ValueError):
                build_database_url({"DATABASE_URL":
                    f"postgresql://unit_test@ep-test.aws.neon.tech/unit?sslmode={mode}"})

    def test_tls_explicito_certificado_e_conflitos(self):
        url = build_database_url({**self.env, "DB_SSLMODE": "verify-full", "DB_SSLROOTCERT": "/unit/ca.crt"})
        self.assertEqual(url.query["sslrootcert"], "/unit/ca.crt")
        with self.assertRaises(ValueError):
            build_database_url({"DATABASE_URL": "postgresql://unit_test@example.invalid/unit?sslmode=require",
                                "DB_SSLMODE": "disable"})

    def test_pool_null_e_pooler(self):
        env = {"DATABASE_URL": "postgresql://unit_test@ep-test-pooler.aws.neon.tech/unit", "DB_POOL_MODE": "null"}
        opts = engine_options(build_database_url(env), env)
        self.assertIs(opts["poolclass"], NullPool)
        self.assertIsNone(opts["connect_args"]["prepare_threshold"])

    def test_migracao_nao_usa_conexao_da_api(self):
        with self.assertRaises(ValueError):
            build_migration_url(self.env)
        with self.assertRaises(ValueError):
            build_migration_url({"MIGRATION_DATABASE_URL": "postgresql://unit_test@ep-test-pooler.aws.neon.tech/unit"})
        url = build_migration_url({"MIGRATION_DATABASE_URL": "postgresql://unit_test@localhost/artx_crm_teste_baseline"})
        self.assertIs(engine_options(url, {}, migration=True)["poolclass"], NullPool)

    def test_erros_nao_revelam_url(self):
        secret = "sensitive-synthetic-marker"
        for raw in (f"postgresql://unit:{secret}@example.invalid:notaport/unit",
                    f"mysql://unit:{secret}@example.invalid/unit"):
            with self.assertRaises(ValueError) as result:
                build_database_url({"DATABASE_URL": raw})
            self.assertNotIn(secret, str(result.exception))
            self.assertNotIn(raw, str(result.exception))

    def test_parametros_invalidos(self):
        for key, value in (("DB_PORT", "0"), ("DB_POOL_SIZE", "0"),
                           ("DB_MAX_OVERFLOW", "-1"), ("DB_CONNECT_TIMEOUT", "x"),
                           ("DB_POOL_MODE", "unknown"), ("DB_PREPARE_THRESHOLD", "-1")):
            env = {**self.env, key: value}
            with self.assertRaises(ValueError):
                engine_options(build_database_url(env), env)

    def test_import_database_e_lazy_e_nao_le_credenciais_reais(self):
        with patch.dict(os.environ, self.env, clear=True), patch("dotenv.load_dotenv", return_value=False):
            sys.modules.pop("database", None)
            database = importlib.import_module("database")
            self.assertEqual(database.engine.url.database, "isolated_not_used")
            self.assertTrue(database.engine.pool._pre_ping)
            database.engine.dispose()
            sys.modules.pop("database", None)

    def test_libpq_compativel_com_certificados_system(self):
        self.assertGreaterEqual(psycopg.pq.version(), 170000)
