"""Validacao de encerramento, competencias e metas; nao executado nesta etapa."""
from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


def _mes_anterior(ano, mes):
    return (ano - 1, 12) if mes == 1 else (ano, mes - 1)


def _mes_seguinte(ano, mes):
    return (ano + 1, 1) if mes == 12 else (ano, mes + 1)


def _faturamento(client, ano, mes):
    resposta = client.get(f"/clientes/faturamento/mensal?ano={ano}&mes={mes}")
    assert resposta.status_code == 200, f"faturamento {ano}-{mes:02d}: HTTP {resposta.status_code}; resposta={resposta.text}"
    return resposta.json()


def test_encerramento_competencia_novos_contratos_e_metas(client, test_engine):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    ano_ant, mes_ant = _mes_anterior(ano, mes)
    ano_prox, mes_prox = _mes_seguinte(ano, mes)
    prefixo = client.test_lead_prefix + "FINANCEIRO"
    cliente_ids = []
    meta_ids = []

    try:
        # A meta precisa existir: respostas 404 não podem ser ignoradas.
        meta = client.post("/metas", json={
            "ano": ano,
            "mes": mes,
            "meta_prospeccoes": 999,
            "meta_reunioes": 999,
            "meta_faturamento": 999999,
        })
        assert meta.status_code == 201, f"POST /metas: HTTP {meta.status_code}; resposta={meta.text}"
        meta_ids.append(meta.json()["id"])

        antes_ant = _faturamento(client, ano_ant, mes_ant)["faturamento_recorrente"]
        antes_atual = _faturamento(client, ano, mes)["faturamento_recorrente"]
        antes_prox = _faturamento(client, ano_prox, mes_prox)["faturamento_recorrente"]
        antes_novos = client.get(f"/metas/faturamento?ano={ano}&mes={mes}")
        assert antes_novos.status_code == 200, antes_novos.text
        novos_antes = antes_novos.json()["novos_faturamentos"]

        criado = client.post("/clientes", json={
            "nome_empresa": prefixo,
            "nicho": "TESTE",
            "telefone": "5500000000000",
            "email": f"{client.test_run_id}-financeiro@example.invalid",
            "valor_mensal": 1000,
            "data_inicio": date(ano_ant, mes_ant, 1).isoformat(),
        })
        assert criado.status_code == 201, f"POST /clientes: HTTP {criado.status_code}; resposta={criado.text}"
        cliente_id = criado.json()["id"]
        cliente_ids.append(cliente_id)

        atual = _faturamento(client, ano, mes)
        historico = _faturamento(client, ano_ant, mes_ant)
        assert atual["faturamento_recorrente"] == antes_atual + 1000
        assert historico["faturamento_recorrente"] == antes_ant + 1000

        reajuste = client.patch(f"/clientes/{cliente_id}", json={"valor_mensal": 1500})
        assert reajuste.status_code == 200, f"PATCH cliente: HTTP {reajuste.status_code}; resposta={reajuste.text}"
        depois_reajuste = _faturamento(client, ano, mes)
        historico_depois = _faturamento(client, ano_ant, mes_ant)
        assert depois_reajuste["faturamento_recorrente"] == antes_atual + 1500
        assert historico_depois["faturamento_recorrente"] == antes_ant + 1000

        novos = client.get(f"/metas/faturamento?ano={ano}&mes={mes}")
        assert novos.status_code == 200, novos.text
        assert novos.json()["novos_faturamentos"] == novos_antes

        encerrado = client.patch(f"/clientes/{cliente_id}/encerrar")
        assert encerrado.status_code == 200, f"encerramento: HTTP {encerrado.status_code}; resposta={encerrado.text}"
        encerrado_mes = _faturamento(client, ano, mes)
        proximo_mes = _faturamento(client, ano_prox, mes_prox)
        assert encerrado_mes["faturamento_recorrente"] == depois_reajuste["faturamento_recorrente"]
        assert proximo_mes["faturamento_recorrente"] == antes_prox

        historico_endpoint = client.get(f"/clientes/{cliente_id}/historico-valores")
        assert historico_endpoint.status_code == 200, historico_endpoint.text
        assert len(historico_endpoint.json()) == 2

        progresso = client.get(f"/metas/progresso/faturamento?ano={ano}&mes={mes}")
        dashboard = client.get(f"/metas/dashboard?ano={ano}&mes={mes}")
        assert progresso.status_code == 200, progresso.text
        assert dashboard.status_code == 200, dashboard.text
        assert progresso.json()["faturamento_recorrente"] == encerrado_mes["faturamento_recorrente"]
        assert dashboard.json()["faturamento"]["faturamento_recorrente"] == progresso.json()["faturamento_recorrente"]
    finally:
        from models import Cliente, ClienteValorMensal, Meta
        db = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)()
        try:
            if cliente_ids:
                db.query(ClienteValorMensal).filter(ClienteValorMensal.cliente_id.in_(cliente_ids)).delete(synchronize_session=False)
                db.query(Cliente).filter(Cliente.id.in_(cliente_ids)).delete(synchronize_session=False)
            if meta_ids:
                db.query(Meta).filter(Meta.id.in_(meta_ids)).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
