"""Integration-test fixtures. Never fall back to the application DATABASE_URL."""
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

BACKEND = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(BACKEND))

TARGET_DATABASE = "artx_crm_teste_baseline"
TEST_YEAR_RANGE = range(2090, 2101)


def _test_url():
    raw = os.getenv("TEST_DATABASE_URL", "").strip()
    if not raw:
        pytest.fail("Defina TEST_DATABASE_URL exclusivamente para artx_crm_teste_baseline.")
    url = make_url(raw)
    if url.database != TARGET_DATABASE:
        pytest.fail("TEST_DATABASE_URL deve apontar exatamente para artx_crm_teste_baseline.")
    if (url.host or "").lower() not in {"localhost", "127.0.0.1", "::1"}:
        pytest.fail("Testes de integração aceitam somente PostgreSQL local.")
    return url


@pytest.fixture(scope="session")
def test_engine():
    url = _test_url()
    engine = create_engine(url, pool_pre_ping=True, poolclass=__import__("sqlalchemy.pool", fromlist=["NullPool"]).NullPool)
    engine.integration_errors = []

    @event.listens_for(engine, "handle_error")
    def capture_integration_error(exception_context):
        original = exception_context.original_exception
        diagnostic = getattr(original, "diag", None)
        engine.integration_errors.append({
            "sqlstate": getattr(original, "sqlstate", None),
            "constraint": getattr(diagnostic, "constraint_name", None),
            "column": getattr(diagnostic, "column_name", None),
            "message": str(original).splitlines()[0][:300],
        })

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def client(test_engine):
    # Import only after the destination guard has passed.
    from main import app
    token = secrets.token_urlsafe(32)
    # Authentication is intentionally supplied by the test fixture, not by production code.
    from auth import hash_token
    from auth_models import SessaoUsuario, Usuario
    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    import database
    database.SessionLocal = Session
    import main as main_module
    main_module.SessionLocal = Session
    run_id = secrets.token_hex(12)
    prefix = f"INTEGRATION_ARTX_{run_id}_"
    db = Session()
    email = f"integration-{run_id}@example.invalid"
    user = Usuario(nome="Integration Admin", email=email, senha_hash=None,
                   tipo="ADMIN", status_acesso="APROVADO", email_verificado=True, ativo=True)
    db.add(user)
    db.flush()
    user_id = user.id
    db.add(SessaoUsuario(token_hash=hash_token(token), usuario_id=user.id,
                         expira_em=datetime.now() + timedelta(hours=1)))
    db.commit()
    db.close()
    try:
        with TestClient(app, base_url="http://localhost") as http:
            http.cookies.set("artx_session", token)
            http.headers.update({"Origin": "http://localhost:3000"})
            http.test_run_id = run_id
            http.test_lead_prefix = prefix
            http.test_meta_ids = []
            http.integration_errors = test_engine.integration_errors
            yield http
    finally:
        db = Session()
        from models import Lead, HistoricoLead, Reuniao
        from models import Meta
        ids = [row[0] for row in db.query(Lead.id).filter(Lead.nome_empresa.like(prefix + "%")).all()]
        try:
            if ids:
                db.query(Reuniao).filter(Reuniao.lead_id.in_(ids)).delete(synchronize_session=False)
        except Exception:
            db.rollback()
        try:
            meta_ids = getattr(http, "test_meta_ids", [])
            if meta_ids:
                db.query(Meta).filter(Meta.id.in_(meta_ids)).delete(synchronize_session=False)
                db.commit()
        except Exception:
            db.rollback()
        try:
            if ids:
                db.query(HistoricoLead).filter(HistoricoLead.lead_id.in_(ids)).delete(synchronize_session=False)
        except Exception:
            db.rollback()
        try:
            if ids:
                db.query(Lead).filter(Lead.id.in_(ids)).delete(synchronize_session=False)
        except Exception:
            db.rollback()
        try:
            db.query(SessaoUsuario).filter(SessaoUsuario.usuario_id == user_id).delete()
            db.query(Usuario).filter(Usuario.id == user_id).delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


@pytest.fixture()
def available_meta_period(test_engine):
    """Find a free reserved competence without touching existing metas."""
    from models import Meta

    Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    db = Session()
    try:
        used = {(row.ano, row.mes) for row in db.query(Meta.ano, Meta.mes).filter(
            Meta.ano.in_(list(TEST_YEAR_RANGE))
        ).all()}
    finally:
        db.close()
    for ano in TEST_YEAR_RANGE:
        for mes in range(1, 13):
            if (ano, mes) not in used:
                return ano, mes
    pytest.fail("Nenhuma competência livre no intervalo reservado de testes (2090-2100).")
