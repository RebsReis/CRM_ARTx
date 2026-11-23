import pytest

pytestmark = pytest.mark.integration


def test_importacao_ignora_duplicados_do_banco_e_do_lote(client):
    prefixo = client.test_lead_prefix
    run = client.test_run_id
    telefone_existente = "55" + str(int(run, 16) % 10**11).zfill(11)
    existente = client.post("/leads", json={
        "nome_empresa": prefixo + "EXISTENTE",
        "email": f"existente-{run}@example.invalid",
        "telefone": telefone_existente,
    })
    assert existente.status_code == 201

    formatado = f"+{telefone_existente[:2]} ({telefone_existente[2:4]}) {telefone_existente[4:9]}-{telefone_existente[9:]}"
    resposta = client.post("/leads/importar", json={"leads": [
        {"linha": 2, "nome_empresa": f"  {prefixo}NOVO  ", "email": f" Novo-{run}@Example.invalid ",
         "fase": "FOLLOW_UP", "nicho": " "},
        {"linha": 3, "nome_empresa": prefixo + "EMAIL_REPETIDO", "email": f"EXISTENTE-{run}@example.invalid"},
        {"linha": 4, "nome_empresa": prefixo + "TEL_REPETIDO", "telefone": formatado},
        {"linha": 5, "nome_empresa": prefixo + "REPETIDO_NO_LOTE", "email": f"novo-{run}@example.invalid"},
        {"linha": 6, "nome_empresa": "   "},
    ]})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["importados"] == 1
    assert [i["linha"] for i in corpo["ignorados"]] == [3, 4, 5, 6]
    novo = corpo["leads"][0]
    assert novo["nome_empresa"] == prefixo + "NOVO"
    assert novo["email"] == f"novo-{run}@example.invalid"
    assert novo["fase"] == "FOLLOW_UP"
    assert novo["nicho"] is None

    ativos = {lead["id"] for lead in client.get("/leads").json()}
    assert novo["id"] in ativos


def test_importacao_rejeita_fase_invalida_sem_salvar_nada(client):
    prefixo = client.test_lead_prefix
    resposta = client.post("/leads/importar", json={"leads": [
        {"linha": 2, "nome_empresa": prefixo + "OK"},
        {"linha": 3, "nome_empresa": prefixo + "RUIM", "fase": "INEXISTENTE"},
    ]})
    assert resposta.status_code == 422
    nomes = {lead["nome_empresa"] for lead in client.get("/leads").json()}
    assert prefixo + "OK" not in nomes


def test_importacao_exige_ao_menos_um_lead(client):
    assert client.post("/leads/importar", json={"leads": []}).status_code == 422
