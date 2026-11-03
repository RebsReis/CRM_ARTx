"""Unit tests for migration-target protection; not executed automatically here."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))
from db_config import build_migration_url


def _env(url):
    return {"MIGRATION_DATABASE_URL": url}


def test_migration_target_accepts_only_isolated_database():
    url = build_migration_url(_env("postgresql+psycopg://postgres@localhost:5432/artx_crm_teste_baseline"))
    assert url.database == "artx_crm_teste_baseline"


@pytest.mark.parametrize("database", ["CRM_artX", "postgres", "artx_crm"])
def test_migration_target_rejects_other_databases(database):
    with pytest.raises(ValueError):
        build_migration_url(_env(f"postgresql+psycopg://postgres@localhost:5432/{database}"))


def test_migration_target_rejects_remote_host():
    with pytest.raises(ValueError):
        build_migration_url(_env("postgresql+psycopg://postgres@db.example.invalid:5432/artx_crm_teste_baseline"))


def test_migration_target_requires_explicit_url():
    with pytest.raises(ValueError):
        build_migration_url({})


def test_migration_target_rejects_invalid_driver_and_parameters():
    with pytest.raises(ValueError):
        build_migration_url(_env("mysql+pymysql://postgres@localhost:5432/artx_crm_teste_baseline"))
    with pytest.raises(ValueError):
        build_migration_url(_env("postgresql+psycopg://postgres@localhost:5432/artx_crm_teste_baseline?sslmode=invalid"))


PRODUCAO = "ep-unit-123.sa-east-1.aws.neon.tech/artx_crm"


def test_production_target_requires_explicit_release():
    with pytest.raises(ValueError):
        build_migration_url(_env(f"postgresql://unit@{PRODUCAO}"))


def test_production_target_accepts_only_declared_host_and_database():
    env = {**_env(f"postgresql://unit@{PRODUCAO}"), "MIGRATION_PRODUCTION_TARGET": PRODUCAO}
    url = build_migration_url(env)
    assert url.database == "artx_crm" and url.query["sslmode"] == "verify-full"
    for outro in ("ep-outro.sa-east-1.aws.neon.tech/artx_crm", "ep-unit-123.sa-east-1.aws.neon.tech/outro"):
        with pytest.raises(ValueError):
            build_migration_url({**env, "MIGRATION_DATABASE_URL": f"postgresql://unit@{outro}"})


def test_production_target_rejects_pooler_and_plaintext():
    env = {"MIGRATION_PRODUCTION_TARGET": "db.unit.invalid/artx_crm"}
    with pytest.raises(ValueError):
        build_migration_url({**env, **_env("postgresql://unit@db.unit.invalid/artx_crm")})
    url = build_migration_url({**env, **_env("postgresql://unit@db.unit.invalid/artx_crm?sslmode=require")})
    assert url.host == "db.unit.invalid"
    neon = {"MIGRATION_PRODUCTION_TARGET": PRODUCAO}
    with pytest.raises(ValueError):
        build_migration_url({**neon, **_env("postgresql://unit@ep-unit-123-pooler.sa-east-1.aws.neon.tech/artx_crm")})


@pytest.mark.parametrize("alvo", ["localhost/CRM_artX", "127.0.0.1/CRM_artX", "sem-banco", "host/a/b"])
def test_production_target_cannot_point_to_local_or_be_malformed(alvo):
    with pytest.raises(ValueError):
        build_migration_url({"MIGRATION_PRODUCTION_TARGET": alvo,
                             **_env("postgresql+psycopg://postgres@localhost:5432/CRM_artX")})


def test_bootstrap_accepts_pooler_of_declared_production_target():
    from db_config import build_database_url, production_target_authorized
    url = build_database_url({"DATABASE_URL": "postgresql://unit@ep-unit-123-pooler.sa-east-1.aws.neon.tech/artx_crm"})
    assert production_target_authorized(url, {"MIGRATION_PRODUCTION_TARGET": PRODUCAO})
    assert not production_target_authorized(url, {})
