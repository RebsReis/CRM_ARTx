"""Redefinicao local e interativa da senha de uma conta; nunca recebe senha por argumento ou imprime hash.

Uso (mesmas variaveis do bootstrap_admin.py):
    $env:MIGRATION_PRODUCTION_TARGET = "host/banco"
    $env:DATABASE_URL = <URL do banco>
    python backend\\redefinir_senha_admin.py
Encerra as sessoes da conta e zera as tentativas de login falhas desse e-mail.
"""
from getpass import getpass

from bootstrap_admin import DATABASE_URL_VALIDADA  # noqa: F401 - valida o destino antes de abrir o banco

from auth import hash_token, hasher
from sqlalchemy import delete, func, select, update
from auth_models import SessaoUsuario, TentativaLogin, TokenEmail, Usuario
from auth_schemas import RedefinirSenha
from database import SessionLocal


def main():
    email = input("E-mail da conta: ").strip().lower()
    senha = getpass("Nova senha (8 a 128 caracteres): ")
    if senha != getpass("Confirme a nova senha: "):
        raise SystemExit("As senhas não conferem; nada foi alterado.")
    try:
        RedefinirSenha(nova_senha=senha)
    except ValueError:
        raise SystemExit("A senha deve ter entre 8 e 128 caracteres; nada foi alterado.")
    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email).with_for_update())
        if usuario is None:
            raise SystemExit("Nenhuma conta com esse e-mail; nada foi alterado.")
        usuario.senha_hash = hasher.hash(senha)
        usuario.atualizado_em = func.localtimestamp()
        db.execute(update(TokenEmail).where(TokenEmail.usuario_id == usuario.id, TokenEmail.usado_em.is_(None)).values(usado_em=func.now()))
        db.execute(delete(SessaoUsuario).where(SessaoUsuario.usuario_id == usuario.id))
        db.execute(delete(TentativaLogin).where(TentativaLogin.chave == hash_token(email)))
        db.commit()
        nome = usuario.nome
    print(f"Senha de {nome} redefinida. Entre no CRM com o e-mail e a nova senha.")


if __name__ == "__main__":
    main()
