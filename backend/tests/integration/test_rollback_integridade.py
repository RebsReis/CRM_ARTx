"""Testes de atomicidade; nao executados nesta etapa."""
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


def _db(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


@pytest.fixture
def rollback_cleanup(test_engine):
    """Registra IDs imediatamente e limpa mesmo quando o teste falha."""
    ids = {"clientes": [], "leads": []}
    yield ids
    from models import Cliente, ClienteValorMensal, HistoricoLead, Lead, Reuniao
    db = _db(test_engine)
    try:
        if ids["clientes"]:
            db.query(ClienteValorMensal).filter(
                ClienteValorMensal.cliente_id.in_(ids["clientes"])
            ).delete(synchronize_session=False)
        if ids["leads"]:
            db.query(Reuniao).filter(Reuniao.lead_id.in_(ids["leads"])).delete(synchronize_session=False)
            db.query(HistoricoLead).filter(HistoricoLead.lead_id.in_(ids["leads"])).delete(synchronize_session=False)
        if ids["clientes"]:
            db.query(Cliente).filter(Cliente.id.in_(ids["clientes"])).delete(synchronize_session=False)
        if ids["leads"]:
            db.query(Lead).filter(Lead.id.in_(ids["leads"])).delete(synchronize_session=False)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _criar_cliente(client, nome, valor=1000):
    resposta = client.post("/clientes", json={
        "nome_empresa": nome,
        "nicho": "TESTE",
        "telefone": "5500000000000",
        "email": f"{client.test_run_id}-{nome.lower()}@example.invalid",
        "valor_mensal": valor,
        "data_inicio": date.today().isoformat(),
    })
    assert resposta.status_code == 201, resposta.text
    return resposta.json()["id"]


def test_falha_apos_flush_no_historico_inicial_faz_rollback(client, test_engine, monkeypatch, rollback_cleanup):
    from models import Cliente, ClienteValorMensal
    import main

    nome = client.test_lead_prefix + "ROLLBACK-CADASTRO"

    def falhar_apos_escrita(db, cliente, **kwargs):
        db.add(ClienteValorMensal(
            cliente_id=cliente.id,
            valor_mensal=cliente.valor_mensal,
            vigencia_inicio=cliente.data_inicio,
            origem="CADASTRO",
        ))
        raise RuntimeError("falha controlada apos flush do historico")

    monkeypatch.setattr(main, "registrar_valor_inicial", falhar_apos_escrita)
    with pytest.raises(Exception):
        client.post("/clientes", json={
            "nome_empresa": nome,
            "nicho": "TESTE",
            "telefone": "5500000000000",
            "email": f"{client.test_run_id}-rollback@example.invalid",
            "valor_mensal": 1000,
        })

    db = _db(test_engine)
    try:
        assert db.query(Cliente).filter(Cliente.nome_empresa == nome).count() == 0
        assert db.query(ClienteValorMensal).join(Cliente).filter(Cliente.nome_empresa == nome).count() == 0
    finally:
        db.close()


def test_falha_na_conversao_nao_arquiva_lead_nem_cria_cliente(client, test_engine, monkeypatch, rollback_cleanup):
    from models import Cliente, Lead
    import main

    lead = client.post("/leads", json={
        "nome_empresa": client.test_lead_prefix + "ROLLBACK-CONVERSAO",
        "nicho": "TESTE",
        "telefone": "5500000000001",
        "email": f"{client.test_run_id}-conversao@example.invalid",
        "fase": "REUNIAO_MARCADA",
    })
    assert lead.status_code == 201, lead.text
    lead_id = lead.json()["id"]
    rollback_cleanup["leads"].append(lead_id)

    def falhar_historico(*args, **kwargs):
        raise RuntimeError("falha controlada na conversao")

    monkeypatch.setattr(main, "registrar_valor_inicial", falhar_historico)
    resposta = client.post(f"/leads/{lead_id}/fechar", json={"valor_mensal": 1500})
    assert resposta.status_code == 500, resposta.text

    db = _db(test_engine)
    try:
        lead_db = db.get(Lead, lead_id)
        assert lead_db is not None
        assert lead_db.arquivado_em is None
        assert db.query(Cliente).filter(Cliente.lead_id == lead_id).count() == 0
    finally:
        db.close()


def test_reajuste_rejeitado_preserva_historico_e_indicador(client, test_engine, rollback_cleanup):
    from models import ClienteValorMensal

    cliente_id = _criar_cliente(client, client.test_lead_prefix + "ROLLBACK-REAJUSTE")
    rollback_cleanup["clientes"].append(cliente_id)
    antes = client.get("/clientes/faturamento/recorrente")
    assert antes.status_code == 200, antes.text
    historico = client.get(f"/clientes/{cliente_id}/historico-valores")
    assert historico.status_code == 200, historico.text
    quantidade = len(historico.json())

    vigencia_reajuste = date.today() + timedelta(days=1)
    primeiro = client.post(f"/clientes/{cliente_id}/reajustes", json={
        "valor_mensal": 1200,
        "vigencia_inicio": vigencia_reajuste.isoformat(),
    })
    assert primeiro.status_code == 201, primeiro.text
    duplicado = client.post(f"/clientes/{cliente_id}/reajustes", json={
        "valor_mensal": 1300,
        "vigencia_inicio": vigencia_reajuste.isoformat(),
    })
    assert duplicado.status_code == 409, duplicado.text

    depois = client.get("/clientes/faturamento/recorrente")
    assert depois.status_code == 200, depois.text
    # O reajuste começa amanhã; o valor vigente hoje e o indicador permanecem iguais.
    assert depois.json()["faturamento_mensal"] == antes.json()["faturamento_mensal"]
    cliente_atual = next(item for item in client.get("/clientes").json() if item["id"] == cliente_id)
    assert float(cliente_atual["valor_mensal"]) == 1000
    historico_depois = client.get(f"/clientes/{cliente_id}/historico-valores")
    assert len(historico_depois.json()) == quantidade + 1

    db = _db(test_engine)
    try:
        assert db.query(ClienteValorMensal).filter(ClienteValorMensal.cliente_id == cliente_id).count() == quantidade + 1
    finally:
        db.close()


def test_falha_no_encerramento_preserva_status_e_data(client, test_engine, monkeypatch, rollback_cleanup):
    import main
    from models import Cliente

    cliente_id = _criar_cliente(client, client.test_lead_prefix + "ROLLBACK-ENCERRAMENTO")
    rollback_cleanup["clientes"].append(cliente_id)
    real_session = _db(test_engine)

    class CommitFailure:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            real_session.close()
            return False

        def __getattr__(self, name):
            return getattr(real_session, name)

        def commit(self):
            raise RuntimeError("falha controlada no commit do encerramento")

    monkeypatch.setattr(main, "SessionLocal", lambda: CommitFailure())
    with pytest.raises(Exception):
        client.patch(f"/clientes/{cliente_id}/encerrar")

    db = _db(test_engine)
    try:
        cliente = db.get(Cliente, cliente_id)
        assert cliente.status == "ATIVO"
        assert cliente.data_encerramento is None
    finally:
        db.close()
