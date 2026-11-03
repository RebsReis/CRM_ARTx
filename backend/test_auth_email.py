"""Testes de recuperacao e verificacao de email, sem envio de mensagens reais."""
import os
import re
import unittest
from unittest.mock import patch
from sqlalchemy import func
import auth
import test_auth as support
from auth_models import TokenEmail

class EmailTest(unittest.TestCase):
    setUpClass = classmethod(support.AutenticacaoTest.setUpClass.__func__)
    tearDownClass = classmethod(support.AutenticacaoTest.tearDownClass.__func__)
    login = support.AutenticacaoTest.login

    def setUp(self):
        support.AutenticacaoTest.setUp(self)
        self.env = patch.dict(os.environ, {"SMTP_HOST": "smtp.test.invalid", "SMTP_FROM": "noreply@example.com"})
        self.env.start()
        self.mail = patch("auth_public.enviar_mensagem")
        self.sender = self.mail.start()

    def tearDown(self):
        self.mail.stop()
        self.env.stop()
        support.AutenticacaoTest.tearDown(self)

    def email_token(self):
        return re.search(r"#token=([A-Za-z0-9_-]+)", self.sender.call_args.args[2]).group(1)

    def test_recuperacao_uso_unico_expiracao_e_sessoes(self):
        self.login("user@example.com")
        response = self.client.post("/auth/recuperacao", json={"email": "user@example.com"})
        self.assertEqual(response.status_code, 202)
        token = self.email_token()
        self.assertNotIn(token, response.text)
        nova = "Outra-senha-segura-1234"
        data = {"token": token, "nova_senha": nova, "confirmacao": nova}
        self.assertEqual(self.client.post("/auth/redefinir", json=data).status_code, 200)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(self.client.post("/auth/redefinir", json=data).status_code, 400)
        self.login("user@example.com", nova)
        self.client.post("/auth/recuperacao", json={"email": "user@example.com"})
        expired = self.email_token()
        with self.sessions() as db:
            db.get(TokenEmail, auth.hash_token(expired)).expira_em = func.now()
            db.commit()
        self.assertEqual(self.client.post("/auth/redefinir", json={**data, "token": expired}).status_code, 400)

    def test_email_alterado_so_apos_confirmacao(self):
        self.login("user@example.com")
        body = {"nome": "Novo nome", "email": "alterado@example.com"}
        self.assertEqual(self.client.patch("/auth/me", json=body).status_code, 400)
        response = self.client.patch("/auth/me", json={**body, "senha_atual": self.senha})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "user@example.com")
        self.assertEqual(self.client.post("/auth/verificar", json={"token": self.email_token()}).status_code, 200)
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.login("alterado@example.com")
