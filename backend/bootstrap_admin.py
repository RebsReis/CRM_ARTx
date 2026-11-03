"""Inicializacao local e interativa; nunca recebe senha por argumento ou imprime hash."""
import os
from pathlib import Path
from getpass import getpass

from dotenv import load_dotenv
from db_config import build_database_url


TARGET_DATABASE = "artx_crm_teste_baseline"
TARGET_HOSTS = {"localhost", "127.0.0.1"}


def validar_destino_antes_do_banco():
    # Reproduz a ordem de carregamento de database.py sem importá-lo antes da validação.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)
    try:
        url = build_database_url()
    except ValueError:
        raise SystemExit("Configuração PostgreSQL ausente ou inválida; nenhum banco foi acessado.") from None
    if (url.host or "").lower() not in TARGET_HOSTS or url.database != TARGET_DATABASE:
        raise SystemExit("Bootstrap permitido somente em localhost/127.0.0.1 e no banco artx_crm_teste_baseline.")
    return url


DATABASE_URL_VALIDADA = validar_destino_antes_do_banco()

from auth import hasher
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from auth_models import Usuario
from auth_schemas import CriarUsuario
from database import SessionLocal


def main():
    nome = input("Nome do administrador: ")
    email = input("E-mail: ")
    senha = getpass("Senha (8 a 128 caracteres): ")
    if senha != getpass("Confirme a senha: "):
        raise SystemExit("As senhas não conferem; nenhum usuário foi alterado.")
    try:
        dados = CriarUsuario(nome=nome, email=email, senha=senha, tipo="ADMIN")
    except ValueError:
        raise SystemExit("Dados inválidos. Confira nome, e-mail e tamanho da senha; nada foi alterado.")
    with SessionLocal() as db:
        db.execute(text("LOCK TABLE usuarios IN SHARE ROW EXCLUSIVE MODE"))
        if db.scalar(select(Usuario.id).where(Usuario.tipo == "ADMIN")) is not None:
            raise SystemExit("Já existe um administrador. Nenhuma senha foi alterada.")
        if db.scalar(select(Usuario.id).where(func.lower(Usuario.email) == str(dados.email))) is not None:
            raise SystemExit("Esse e-mail já existe. Concilie a conta existente sem sobrescrever sua senha.")
        db.add(Usuario(
            nome=dados.nome,
            email=str(dados.email),
            senha_hash=hasher.hash(senha),
            tipo="ADMIN",
            status_acesso="APROVADO",
            email_verificado=True,
            ativo=True,
        ))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise SystemExit("O cadastro conflita com uma conta existente. Nenhuma senha foi alterada.") from None
    print("Administrador criado. Entre no CRM com o e-mail e a senha informados.")


if __name__ == "__main__":
    main()
