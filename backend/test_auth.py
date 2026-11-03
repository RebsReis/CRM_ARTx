"""HTTP integration tests: isolated PostgreSQL schema, no real accounts changed."""
import secrets
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

import auth
import main
import test_prospeccoes as support
from auth_models import SessaoUsuario, TentativaLogin, Usuario
from database import get_db


class AutenticacaoTest(unittest.TestCase):
    tearDownClass = classmethod(support.ProspeccoesPostgresTest.tearDownClass.__func__)

    @classmethod
    def setUpClass(cls):
        support.ProspeccoesPostgresTest.setUpClass.__func__(cls)
        with cls.test_engine.begin() as c:
            sql = Path(__file__).with_name("migrations").joinpath("20261020_usuarios_sessoes.sql").read_text(encoding="utf-8")
            c.execute(text(sql)); c.execute(text(sql))

    def setUp(self):
        def override():
            with self.sessions() as db:
                yield db
        main.app.dependency_overrides[get_db] = override
        self.factory_patch = patch.object(main, "SessionLocal", self.sessions)
        self.factory_patch.start()
        self.senha = secrets.token_urlsafe(20)
        with self.sessions() as db:
            db.execute(delete(SessaoUsuario)); db.execute(delete(TentativaLogin)); db.execute(delete(Usuario))
            admin = Usuario(nome="Admin de teste", email="admin@example.com", senha_hash=auth.hasher.hash(self.senha), tipo="ADMIN", ativo=True)
            user = Usuario(nome="Usuario de teste", email="user@example.com", senha_hash=auth.hasher.hash(self.senha), tipo="USUARIO", ativo=True)
            db.add_all([admin, user]); db.commit(); db.refresh(admin); db.refresh(user)
            self.admin_id, self.user_id = admin.id, user.id
        self.client = TestClient(main.app, headers={"Origin": "http://localhost:3000"})

    def tearDown(self):
        self.client.close()
        main.app.dependency_overrides.clear()
        self.factory_patch.stop()

    def login(self, email="admin@example.com", senha=None):
        response = self.client.post("/auth/login", json={"email": email, "senha": senha or self.senha})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertNotIn("senha", response.text)
        return response

    def test_cadastro_publico_e_google_desabilitados(self):
        removidas = {"/auth/cadastro", "/auth/google/iniciar", "/auth/google/callback", "/auth/conexoes", "/auth/conexoes/google"}
        self.assertTrue(removidas.isdisjoint(main.app.openapi()["paths"]))
        self.login()
        for route in ["/auth/cadastro", "/auth/google/iniciar"]:
            self.assertEqual(self.client.post(route, json={}).status_code, 404)
        self.assertEqual(self.client.get("/auth/google/callback?code=antigo&state=antigo").status_code, 404)

    def test_projeto_finalizado_persiste_e_pode_reabrir(self):
        self.login()
        cliente = self.client.post("/clientes", json={"nome_empresa": "Cliente isolado", "valor_mensal": 100})
        self.assertEqual(cliente.status_code, 201, cliente.text)
        projeto = self.client.post("/projetos", json={"cliente_id": cliente.json()["id"], "nome_projeto": "Projeto isolado"})
        self.assertEqual(projeto.status_code, 201, projeto.text)
        projeto_id = projeto.json()["id"]
        for status in ["EM_ANDAMENTO", "FINALIZADA", "PENDENTE", "FINALIZADA"]:
            resposta = self.client.patch(f"/projetos/{projeto_id}/status", json={"status": status})
            self.assertEqual(resposta.status_code, 200, resposta.text)
            self.assertEqual(resposta.json()["status"], status)
            lista = self.client.get("/projetos").json()
            self.assertEqual(next(p for p in lista if p["id"] == projeto_id)["status"], status)
        antiga = self.client.patch(f"/projetos/{projeto_id}/status", json={"status": "CONCLUIDO"})
        self.assertEqual(antiga.status_code, 200, antiga.text)
        self.assertEqual(antiga.json()["status"], "FINALIZADA")

    def test_anonimo_e_usuario_comum_nao_administram(self):
        self.assertEqual(self.client.get("/usuarios").status_code, 401)
        self.assertEqual(self.client.get("/leads").status_code, 401)
        self.login("user@example.com")
        self.assertEqual(self.client.get("/leads").status_code, 200)
        self.assertEqual(self.client.get("/usuarios").status_code, 403)
        body = {"nome": "Invasor", "email": "bad@example.com", "tipo": "ADMIN", "senha": self.senha}
        self.assertEqual(self.client.post("/usuarios", json=body).status_code, 403)
        self.assertEqual(self.client.put(f"/usuarios/{self.admin_id}", json={"nome": "Outro", "email": "admin@example.com", "tipo": "USUARIO", "ativo": False}).status_code, 403)
        self.assertEqual(self.client.post(f"/usuarios/{self.admin_id}/senha", json={"nova_senha": self.senha}).status_code, 403)
        self.assertEqual(self.client.patch("/auth/me", json={"nome": "Nome", "email": "user@example.com", "tipo": "ADMIN"}).status_code, 422)

    def test_admin_cria_edita_desativa_reativa_e_redefine(self):
        self.login()
        created = self.client.post("/usuarios", json={"nome": "Novo", "email": "NOVO@example.com", "tipo": "USUARIO", "senha": self.senha})
        self.assertEqual(created.status_code, 201, created.text)
        self.assertNotIn("senha", created.text)
        user_id = created.json()["id"]
        body = {"nome": "Editado", "email": "novo@example.com", "tipo": "USUARIO", "ativo": False}
        self.assertEqual(self.client.put(f"/usuarios/{user_id}", json=body).status_code, 200)
        other = TestClient(main.app, headers={"Origin": "http://localhost:3000"})
        self.assertEqual(other.post("/auth/login", json={"email": body["email"], "senha": self.senha}).status_code, 401)
        body["ativo"] = True
        self.assertEqual(self.client.put(f"/usuarios/{user_id}", json=body).status_code, 200)
        self.assertEqual(other.post("/auth/login", json={"email": body["email"], "senha": self.senha}).status_code, 200)
        nova = secrets.token_urlsafe(20)
        self.assertEqual(self.client.post(f"/usuarios/{user_id}/senha", json={"nova_senha": nova}).status_code, 204)
        self.assertEqual(other.get("/auth/me").status_code, 401)
        self.assertEqual(other.post("/auth/login", json={"email": body["email"], "senha": nova}).status_code, 200)
        body["ativo"] = False
        self.client.put(f"/usuarios/{user_id}", json=body)
        self.assertEqual(other.get("/auth/me").status_code, 401)
        other.close()

    def test_senha_propria_dados_pessoais_e_logout(self):
        self.login("user@example.com")
        response = self.client.patch("/auth/me", json={"nome": "Nome atualizado", "email": "user@example.com"})
        self.assertEqual(response.status_code, 200)
        nova = secrets.token_urlsafe(20)
        dados = {"senha_atual": "errada", "nova_senha": nova, "confirmacao": nova}
        self.assertEqual(self.client.post("/auth/senha", json=dados).status_code, 400)
        dados["senha_atual"] = self.senha
        self.assertEqual(self.client.post("/auth/senha", json=dados).status_code, 204)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.login("user@example.com", nova)
        token = self.client.cookies.get(auth.COOKIE)
        self.assertEqual(self.client.post("/auth/logout").status_code, 204)
        self.client.cookies.set(auth.COOKIE, token)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_senhas_nao_expostas_e_cookie_seguro(self):
        response = self.login()
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie); self.assertIn("samesite=lax", cookie)
        public = self.client.get("/usuarios")
        self.assertNotIn("senha", public.text)
        self.assertNotIn("argon2", public.text)
        self.assertNotIn(self.senha, public.text)
        invalid = self.client.post("/usuarios", json={"nome": "Nome", "email": "email-invalido", "tipo": "USUARIO", "senha": "curta"})
        self.assertEqual(invalid.status_code, 422)
        self.assertNotIn("curta", invalid.text)
        with self.sessions() as db:
            user = db.get(Usuario, self.admin_id)
            self.assertTrue(user.senha_hash.startswith("$argon2id$"))
            self.assertNotEqual(db.scalar(select(SessaoUsuario.token_hash)), self.client.cookies.get(auth.COOKIE))

    def test_admin_principal_email_duplicado_e_csrf(self):
        self.login()
        body = {"nome": "Admin", "email": "admin@example.com", "tipo": "USUARIO", "ativo": True}
        self.assertEqual(self.client.put(f"/usuarios/{self.admin_id}", json=body).status_code, 409)
        body.update(tipo="ADMIN", ativo=False)
        self.assertEqual(self.client.put(f"/usuarios/{self.admin_id}", json=body).status_code, 409)
        self.assertEqual(self.client.post("/usuarios", json={"nome": "Duplicado", "email": "ADMIN@example.com", "tipo": "USUARIO", "senha": self.senha}).status_code, 409)
        self.assertEqual(self.client.post("/auth/logout", headers={"Origin": "https://outro.example"}).status_code, 403)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)

    def test_no_maximo_um_admin_em_requisicoes_simultaneas(self):
        self.login()
        token = self.client.cookies.get(auth.COOKIE)
        def tentar(indice):
            with TestClient(main.app, headers={"Origin": "http://localhost:3000", "Cookie": f"{auth.COOKIE}={token}"}) as client:
                return client.post("/usuarios", json={"nome": "Outro admin", "email": f"admin{indice}@example.com", "tipo": "ADMIN", "senha": self.senha}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(tentar, [1, 2]))
        self.assertEqual(results, [409, 409])
        with self.sessions() as db:
            self.assertEqual(len(db.scalars(select(Usuario).where(Usuario.tipo == "ADMIN")).all()), 1)

    def test_limite_tentativas_login(self):
        for _ in range(10):
            self.assertEqual(self.client.post("/auth/login", json={"email": "user@example.com", "senha": "incorreta"}).status_code, 401)
        self.assertEqual(self.client.post("/auth/login", json={"email": "user@example.com", "senha": self.senha}).status_code, 429)


if __name__ == "__main__":
    unittest.main()
