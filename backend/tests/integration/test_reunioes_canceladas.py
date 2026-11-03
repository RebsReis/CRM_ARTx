"""Validacao de reunioes e cancelamento; nao executado nesta etapa."""
from datetime import date

import pytest
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


def test_reunioes_canceladas_e_indicadores(client, test_engine):
    hoje = date.today()
    ano, mes = hoje.year, hoje.month
    prefixo = client.test_lead_prefix + "REUNIOES"
    lead_id = None
    meta_id = None
    try:
        meta = client.post("/metas", json={
            "ano": ano,
            "mes": mes,
            "meta_prospeccoes": 10,
            "meta_reunioes": 10,
            "meta_faturamento": 0,
        })
        assert meta.status_code == 201, f"POST /metas: HTTP {meta.status_code}; resposta={meta.text}"
        meta_id = meta.json()["id"]

        criado = client.post("/leads", json={
            "nome_empresa": prefixo,
            "nicho": "TESTE",
            "telefone": "5500000000000",
            "email": f"{client.test_run_id}-reunioes@example.invalid",
            "fase": "PROSPECTAR",
        })
        assert criado.status_code == 201, criado.text
        lead_id = criado.json()["id"]

        primeira = client.patch(f"/leads/{lead_id}/fase", json={"fase": "REUNIAO_MARCADA"})
        assert primeira.status_code == 200, primeira.text
        repetida = client.patch(f"/leads/{lead_id}/fase", json={"fase": "REUNIAO_MARCADA"})
        assert repetida.status_code == 200, repetida.text

        indicador = client.get(f"/reunioes/indicadores/mensal?ano={ano}&mes={mes}")
        assert indicador.status_code == 200, indicador.text
        assert indicador.json()["reunioes_agendadas"] == 1

        saida = client.patch(f"/leads/{lead_id}/fase", json={"fase": "FOLLOW_UP"})
        assert saida.status_code == 200, saida.text
        retorno = client.patch(f"/leads/{lead_id}/fase", json={"fase": "REUNIAO_MARCADA"})
        assert retorno.status_code == 200, retorno.text

        from models import Reuniao
        db = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)()
        try:
            reunioes = db.query(Reuniao).filter(Reuniao.lead_id == lead_id).order_by(Reuniao.id).all()
            assert len(reunioes) == 2
            reunioes[0].status = "CANCELADA"
            reunioes[1].status = "REALIZADA"
            db.commit()
        finally:
            db.close()

        indicador = client.get(f"/reunioes/indicadores/mensal?ano={ano}&mes={mes}")
        assert indicador.status_code == 200, indicador.text
        assert indicador.json()["reunioes_agendadas"] == 1

        prospeccao = client.get(f"/leads/prospeccoes/mensal?ano={ano}&mes={mes}")
        assert prospeccao.status_code == 200, prospeccao.text
        assert prospeccao.json()["prospeccoes_realizadas"] == 1

        resumo = client.get(f"/metas/reunioes/resumo?ano={ano}&mes={mes}")
        progresso = client.get(f"/metas/progresso/reunioes?ano={ano}&mes={mes}")
        dashboard = client.get(f"/metas/dashboard?ano={ano}&mes={mes}")
        assert resumo.status_code == 200, resumo.text
        assert progresso.status_code == 200, progresso.text
        assert dashboard.status_code == 200, dashboard.text
        assert resumo.json()["reunioes_marcadas"] == 1
        assert progresso.json()["reunioes_realizadas"] == 1
        assert dashboard.json()["reunioes"]["reunioes_realizadas"] == 1

        # O cancelamento altera o status, mas não remove o registro histórico.
        db = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)()
        try:
            assert db.query(Reuniao).filter(Reuniao.lead_id == lead_id).count() == 2
        finally:
            db.close()
    finally:
        from models import HistoricoLead, Lead, Reuniao, Meta
        db = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)()
        try:
            if lead_id:
                db.query(Reuniao).filter(Reuniao.lead_id == lead_id).delete(synchronize_session=False)
                db.query(HistoricoLead).filter(HistoricoLead.lead_id == lead_id).delete(synchronize_session=False)
                db.query(Lead).filter(Lead.id == lead_id).delete(synchronize_session=False)
            if meta_id:
                db.query(Meta).filter(Meta.id == meta_id).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
