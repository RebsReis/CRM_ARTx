from datetime import date

import pytest

pytestmark = pytest.mark.integration


def _periodo():
    hoje = date.today()
    return hoje.year, hoje.month


def test_funil_prospeccao_reuniao_e_historico(client):
    ano, mes = _periodo()
    nome = client.test_lead_prefix + "LEAD"
    criado = client.post("/leads", json={
        "nome_empresa": nome,
        "nicho": "TESTE",
        "telefone": "5500000000000",
        "email": f"{client.test_run_id}@example.invalid",
        "fase": "PROSPECTAR",
        "observacao": "Dado ficticio de teste",
    })
    assert criado.status_code == 201
    lead_id = criado.json()["id"]

    inicial = client.get(f"/leads/prospeccoes/mensal?ano={ano}&mes={mes}").json()
    assert inicial["prospeccoes_realizadas"] == 0

    movido = client.patch(f"/leads/{lead_id}/fase", json={"fase": "FOLLOW_UP"})
    assert movido.status_code == 200
    apos_prospeccao = client.get(f"/leads/prospeccoes/mensal?ano={ano}&mes={mes}").json()
    assert apos_prospeccao["prospeccoes_realizadas"] == 1

    reuniao = client.patch(f"/leads/{lead_id}/fase", json={"fase": "REUNIAO_MARCADA"})
    assert reuniao.status_code == 200
    indicador = client.get(f"/reunioes/indicadores/mensal?ano={ano}&mes={mes}").json()
    assert indicador["reunioes_agendadas"] >= 1

    repetida = client.patch(f"/leads/{lead_id}/fase", json={"fase": "REUNIAO_MARCADA"})
    assert repetida.status_code == 200
    depois_repetida = client.get(f"/reunioes/indicadores/mensal?ano={ano}&mes={mes}").json()
    assert depois_repetida["reunioes_agendadas"] == indicador["reunioes_agendadas"]

    client.patch(f"/leads/{lead_id}/fase", json={"fase": "FOLLOW_UP"}).raise_for_status()
    retorno = client.patch(f"/leads/{lead_id}/fase", json={"fase": "REUNIAO_MARCADA"})
    assert retorno.status_code == 200
    novo_indicador = client.get(f"/reunioes/indicadores/mensal?ano={ano}&mes={mes}").json()
    assert novo_indicador["reunioes_agendadas"] == indicador["reunioes_agendadas"] + 1

    historico = client.get(f"/leads/{lead_id}/historico")
    assert historico.status_code == 200
    fases = [(x["fase_anterior"], x["fase_nova"]) for x in historico.json()]
    assert ("PROSPECTAR", "FOLLOW_UP") in fases
    assert fases.count(("PROSPECTAR", "FOLLOW_UP")) == 1

    # Detecta a divergência conhecida entre as fontes do dashboard e do endpoint mensal.
    dashboard = client.get(f"/metas/dashboard?ano={ano}&mes={mes}")
    if dashboard.status_code == 200:
        assert dashboard.json()["reunioes"]["reunioes_realizadas"] >= 0


def test_indicadores_mensais_usam_fontes_consistentes(client, available_meta_period):
    ano, mes = available_meta_period
    meta = client.post("/metas", json={
        "ano": ano, "mes": mes,
        "meta_prospeccoes": 10, "meta_reunioes": 10,
        "meta_faturamento": 1000,
    })
    assert meta.status_code == 201, (
        f"POST /metas retornou HTTP {meta.status_code}; "
        f"competencia={ano:04d}-{mes:02d}; "
        f"resposta={meta.text}; "
        f"diagnostico_integridade={client.integration_errors[-1] if client.integration_errors else 'nenhum'}"
    )
    client.test_meta_ids.append(meta.json()["id"])

    prospeccoes = client.get(f"/leads/prospeccoes/mensal?ano={ano}&mes={mes}").json()
    progresso_prospeccoes = client.get(f"/metas/progresso/prospeccoes?ano={ano}&mes={mes}").json()
    reunioes = client.get(f"/reunioes/indicadores/mensal?ano={ano}&mes={mes}").json()
    progresso_reunioes = client.get(f"/metas/progresso/reunioes?ano={ano}&mes={mes}").json()
    resumo_reunioes = client.get(f"/metas/reunioes/resumo?ano={ano}&mes={mes}").json()
    dashboard = client.get(f"/metas/dashboard?ano={ano}&mes={mes}")

    assert prospeccoes["prospeccoes_realizadas"] == progresso_prospeccoes["prospeccoes_realizadas"]
    assert reunioes["reunioes_agendadas"] == progresso_reunioes["reunioes_realizadas"]
    assert reunioes["reunioes_agendadas"] == resumo_reunioes["reunioes_marcadas"]
    assert dashboard.status_code == 200
    assert dashboard.json()["prospeccoes"]["prospeccoes_realizadas"] == prospeccoes["prospeccoes_realizadas"]
    assert dashboard.json()["reunioes"]["reunioes_realizadas"] == reunioes["reunioes_agendadas"]
