from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


def _periodo_atual():
    hoje = date.today()
    return hoje.year, hoje.month


def test_clientes_faturamento_e_conversao(client, test_engine):
    ano, mes = _periodo_atual()
    if mes == 1:
        ano_anterior, mes_anterior = ano - 1, 12
    else:
        ano_anterior, mes_anterior = ano, mes - 1
    prefixo = client.test_lead_prefix + "CLIENTE"
    cliente_ids = []
    lead_ids = []

    try:
        criado = client.post("/clientes", json={
            "nome_empresa": prefixo,
            "nicho": "TESTE",
            "telefone": "5500000000000",
            "email": f"{client.test_run_id}-cliente@example.invalid",
            "valor_mensal": 1000,
            "data_inicio": date(ano_anterior, mes_anterior, 1).isoformat(),
        })
        assert criado.status_code == 201, criado.text
        cliente_id = criado.json()["id"]
        cliente_ids.append(cliente_id)

        recorrente = client.get("/clientes/faturamento/recorrente")
        assert recorrente.status_code == 200, f"GET /clientes/faturamento/recorrente: HTTP {recorrente.status_code}; resposta={recorrente.text}"
        assert recorrente.json()["faturamento_mensal"] >= 1000

        mensal = client.get(f"/clientes/faturamento/mensal?ano={ano}&mes={mes}")
        assert mensal.status_code == 200, f"GET /clientes/faturamento/mensal: HTTP {mensal.status_code}; resposta={mensal.text}"
        assert mensal.json()["faturamento_recorrente"] >= 1000

        mensal_anterior = client.get(f"/clientes/faturamento/mensal?ano={ano_anterior}&mes={mes_anterior}")
        assert mensal_anterior.status_code == 200, f"GET /clientes/faturamento/mensal: HTTP {mensal_anterior.status_code}; resposta={mensal_anterior.text}"
        anterior = mensal_anterior.json()["faturamento_recorrente"]
        alterado = client.patch(f"/clientes/{cliente_id}", json={"valor_mensal": 2000})
        assert alterado.status_code == 200, f"PATCH /clientes/{cliente_id}: HTTP {alterado.status_code}; resposta={alterado.text}"
        mensal_posterior = client.get(f"/clientes/faturamento/mensal?ano={ano}&mes={mes}")
        assert mensal_posterior.status_code == 200, f"GET /clientes/faturamento/mensal: HTTP {mensal_posterior.status_code}; resposta={mensal_posterior.text}"
        posterior = mensal_posterior.json()["faturamento_recorrente"]
        assert posterior >= 2000
        mensal_anterior_depois = client.get(f"/clientes/faturamento/mensal?ano={ano_anterior}&mes={mes_anterior}")
        assert mensal_anterior_depois.status_code == 200, mensal_anterior_depois.text
        assert mensal_anterior_depois.json()["faturamento_recorrente"] == anterior

        # Documenta o comportamento atual: o valor alterado afeta retroativamente a competência.
        # Encerramento durante a competência mantém seu faturamento integral.
        encerrado = client.patch(f"/clientes/{cliente_id}/encerrar")
        assert encerrado.status_code == 200, f"PATCH /clientes/{cliente_id}/encerrar: HTTP {encerrado.status_code}; resposta={encerrado.text}"
        mensal_encerrado = client.get(f"/clientes/faturamento/mensal?ano={ano}&mes={mes}")
        assert mensal_encerrado.status_code == 200, f"GET /clientes/faturamento/mensal: HTTP {mensal_encerrado.status_code}; resposta={mensal_encerrado.text}"
        depois_encerramento = mensal_encerrado.json()["faturamento_recorrente"]
        assert depois_encerramento == posterior

        lead = client.post("/leads", json={
            "nome_empresa": prefixo + "-LEAD",
            "nicho": "TESTE",
            "telefone": "5500000000001",
            "email": f"{client.test_run_id}-lead@example.invalid",
            "fase": "PROSPECTAR",
            "observacao": "Conversao ficticia",
        })
        assert lead.status_code == 201, lead.text
        lead_id = lead.json()["id"]
        lead_ids.append(lead_id)
        assert client.patch(f"/leads/{lead_id}/fase", json={"fase": "REUNIAO_MARCADA"}).status_code == 200

        convertido = client.post(f"/leads/{lead_id}/fechar", json={"valor_mensal": 1500})
        assert convertido.status_code == 200, convertido.text
        convertido_id = convertido.json()["cliente_id"]
        cliente_ids.append(convertido_id)

        leads = client.get("/leads").json()
        assert all(item["id"] != lead_id for item in leads)

        metas_faturamento = client.get(f"/metas/progresso/faturamento?ano={ano}&mes={mes}")
        dashboard = client.get(f"/metas/dashboard?ano={ano}&mes={mes}")
        if metas_faturamento.status_code == 200 and dashboard.status_code == 200:
            assert dashboard.json()["faturamento"]["faturamento_recorrente"] == metas_faturamento.json()["faturamento_recorrente"]

        invalido = client.post("/clientes", json={
            "nome_empresa": prefixo + "-INVALIDO",
            "nicho": "TESTE",
            "telefone": "5500000000002",
            "email": f"{client.test_run_id}-invalid@example.invalid",
            "valor_mensal": -1,
        })
        assert invalido.status_code in {400, 422}
    finally:
        from models import Cliente, HistoricoLead, Lead, Reuniao

        Session = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
        db = Session()
        try:
            if cliente_ids:
                from models import ClienteValorMensal
                db.query(ClienteValorMensal).filter(ClienteValorMensal.cliente_id.in_(cliente_ids)).delete(synchronize_session=False)
                db.query(Cliente).filter(Cliente.id.in_(cliente_ids)).delete(synchronize_session=False)
            if lead_ids:
                db.query(Reuniao).filter(Reuniao.lead_id.in_(lead_ids)).delete(synchronize_session=False)
                db.query(HistoricoLead).filter(HistoricoLead.lead_id.in_(lead_ids)).delete(synchronize_session=False)
                db.query(Lead).filter(Lead.id.in_(lead_ids)).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
