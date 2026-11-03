"""Cenarios de autenticacao/autorizacao; nao executados nesta etapa."""
from datetime import datetime, timedelta
import secrets

import pytest
from sqlalchemy import func, text
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


def _sessao(test_engine):
    return sessionmaker(bind=test_engine, autoflush=False, autocommit=False)()


def _criar_usuario(test_engine, *, status="APROVADO", ativo=True):
    from auth import hash_token, hasher
    from auth_models import SessaoUsuario, Usuario

    db = _sessao(test_engine)
    run_id = secrets.token_hex(10)
    token = secrets.token_urlsafe(32)
    usuario = Usuario(
        nome=f"Integration Security {run_id}",
        email=f"security-{run_id}@example.invalid",
        senha_hash=hasher.hash(secrets.token_urlsafe(24)),
        tipo="USUARIO",
        status_acesso=status,
        email_verificado=True,
        ativo=ativo,
    )
    db.add(usuario)
    db.flush()
    usuario_id = usuario.id
    db.add(SessaoUsuario(
        token_hash=hash_token(token),
        usuario_id=usuario_id,
        expira_em=datetime.now() + timedelta(hours=1),
    ))
    db.commit()
    db.close()
    return usuario_id, token


def test_endpoints_protegidos_rejeitam_sessao_ausente_e_invalida(client):
    client.cookies.delete("artx_session")
    for path in ("/clientes", "/metas/dashboard?ano=2090&mes=1"):
        resposta = client.get(path)
        assert resposta.status_code == 401, f"{path}: HTTP {resposta.status_code}; resposta={resposta.text}"
    resposta = client.post("/clientes", json={"nome_empresa": "INTEGRATION-NO-SESSION", "valor_mensal": 1})
    assert resposta.status_code == 401, resposta.text

    client.cookies.set("artx_session", "token-invalido")
    resposta = client.get("/clientes")
    assert resposta.status_code == 401, resposta.text


def test_sessao_expirada_pendente_e_usuario_inativo(client, test_engine):
    from auth import hash_token
    from auth_models import SessaoUsuario

    criados = []
    try:
        for status, ativo in (("PENDENTE", True), ("APROVADO", False)):
            usuario_id, token = _criar_usuario(test_engine, status=status, ativo=ativo)
            criados.append(usuario_id)
            client.cookies.set("artx_session", token)
            resposta = client.get("/clientes")
            assert resposta.status_code == 401, f"status={status}, ativo={ativo}: {resposta.text}"

        # Sessao aprovada, mas expirada, tambem nao pode acessar o CRM.
        usuario_id, token = _criar_usuario(test_engine)
        criados.append(usuario_id)
        db = _sessao(test_engine)
        db.query(SessaoUsuario).filter(
            SessaoUsuario.usuario_id == usuario_id,
            SessaoUsuario.token_hash == hash_token(token),
        ).update({SessaoUsuario.expira_em: func.now() - text("INTERVAL '1 minute'")})
        db.commit()
        db.close()
        client.cookies.set("artx_session", token)
        resposta = client.get("/clientes")
        assert resposta.status_code == 401, resposta.text
    finally:
        from auth_models import SessaoUsuario, Usuario
        db = _sessao(test_engine)
        try:
            if criados:
                db.query(SessaoUsuario).filter(SessaoUsuario.usuario_id.in_(criados)).delete(synchronize_session=False)
                db.query(Usuario).filter(Usuario.id.in_(criados)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_usuario_aprovado_ativo_com_sessao_valida_acessa_crm(client, test_engine):
    usuario_id, token = _criar_usuario(test_engine, status="APROVADO", ativo=True)
    try:
        client.cookies.set("artx_session", token)
        resposta = client.get("/clientes")
        assert resposta.status_code == 200, resposta.text
    finally:
        from auth_models import SessaoUsuario, Usuario
        db = _sessao(test_engine)
        try:
            db.query(SessaoUsuario).filter(SessaoUsuario.usuario_id == usuario_id).delete(synchronize_session=False)
            db.query(Usuario).filter(Usuario.id == usuario_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()


def test_origem_nao_autorizada_e_operacoes_sem_autorizacao(client):
    client.headers.update({"Origin": "https://origem-nao-autorizada.invalid"})
    resposta = client.post("/clientes", json={"nome_empresa": "INTEGRATION-UNAUTHORIZED", "valor_mensal": 1})
    assert resposta.status_code == 403, resposta.text

    resposta = client.post("/clientes/1/reajustes", json={"valor_mensal": 2})
    assert resposta.status_code == 403, resposta.text


def test_usuario_comum_nao_acessa_funcoes_de_administrador(client, test_engine):
    usuario_id, token = _criar_usuario(test_engine)
    try:
        client.cookies.set("artx_session", token)
        resposta = client.get("/usuarios")
        assert resposta.status_code == 403, resposta.text
    finally:
        from auth_models import SessaoUsuario, Usuario
        db = _sessao(test_engine)
        try:
            db.query(SessaoUsuario).filter(SessaoUsuario.usuario_id == usuario_id).delete(synchronize_session=False)
            db.query(Usuario).filter(Usuario.id == usuario_id).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()

