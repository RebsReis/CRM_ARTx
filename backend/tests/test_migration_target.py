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
