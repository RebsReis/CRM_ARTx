from datetime import date, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

pytestmark = pytest.mark.integration


def test_historico_reajuste_e_competencia(client, test_engine):
    prefix = client.test_lead_prefix + "HISTORICO"
    cliente_ids = []
    try:
        inicio = date.today()
        criado = client.post("/clientes", json={
            "nome_empresa": prefix,
            "nicho": "TESTE",
            "telefone": "5500000000000",
            "email": f"{client.test_run_id}-historico@example.invalid",
            "valor_mensal": 1000,
            "data_inicio": inicio.isoformat(),
        })
        assert criado.status_code == 201, criado.text
        cliente_id = criado.json()["id"]
        cliente_ids.append(cliente_id)

        atual = client.get(f"/clientes/{cliente_id}/historico-valores")
        assert atual.status_code == 200, atual.text
        assert len(atual.json()) == 1
        assert atual.json()[0]["origem"] == "CADASTRO"

        futuro = (inicio + timedelta(days=31)).replace(day=1)
        reajuste = client.post(f"/clientes/{cliente_id}/reajustes", json={
            "valor_mensal": 1500,
            "vigencia_inicio": futuro.isoformat(),
        })
        assert reajuste.status_code == 201, reajuste.text
        historico = client.get(f"/clientes/{cliente_id}/historico-valores")
        assert historico.status_code == 200
        assert len(historico.json()) == 2

        # A competência futura consulta a vigência futura, sem antecipar o valor atual.
        mensal_futuro = client.get(
            f"/clientes/faturamento/mensal?ano={futuro.year}&mes={futuro.month}"
        )
        assert mensal_futuro.status_code == 200, mensal_futuro.text
        assert mensal_futuro.json()["faturamento_recorrente"] >= 1500

        # O valor atual permanece o vigente hoje; o reajuste futuro não o antecipa.
        cliente_atual = client.get(f"/clientes").json()
        registro_atual = next(item for item in cliente_atual if item["id"] == cliente_id)
        assert float(registro_atual["valor_mensal"]) == 1000

        sobreposto = client.post(f"/clientes/{cliente_id}/reajustes", json={
            "valor_mensal": 1700,
            "vigencia_inicio": futuro.isoformat(),
        })
        assert sobreposto.status_code == 409, sobreposto.text

        patch_financeiro = client.patch(f"/clientes/{cliente_id}", json={"valor_mensal": 1200})
        assert patch_financeiro.status_code == 409, patch_financeiro.text

        retroativo = client.post(f"/clientes/{cliente_id}/reajustes", json={
            "valor_mensal": 900,
            "vigencia_inicio": (inicio - timedelta(days=1)).isoformat(),
        })
        assert retroativo.status_code == 400, retroativo.text
    finally:
        from models import Cliente, ClienteValorMensal
        db = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)()
        try:
            if cliente_ids:
                db.query(ClienteValorMensal).filter(ClienteValorMensal.cliente_id.in_(cliente_ids)).delete(synchronize_session=False)
                db.query(Cliente).filter(Cliente.id.in_(cliente_ids)).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
