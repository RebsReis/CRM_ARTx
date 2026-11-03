import os
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from auth import administrador, confirmar, hash_token, hasher, invalidar_sessoes
from auth_models import TentativaLogin, TokenEmail, Usuario
from auth_schemas import AprovarUsuario, ConfirmarToken, RecuperarSenha, SolicitarEmail, UsuarioPublico
from database import get_db

router = APIRouter(tags=["Cadastro e recuperacao"])
PUBLIC_URL = os.getenv("APP_PUBLIC_URL", "http://localhost:3000").rstrip("/")


def enviar_mensagem(destino: str, assunto: str, corpo: str):
    host, remetente = os.getenv("SMTP_HOST"), os.getenv("SMTP_FROM")
    modo = os.getenv("SMTP_SECURITY", "starttls")
    if not host or not remetente or modo not in {"ssl", "starttls"}:
        raise HTTPException(503, "O envio de e-mail ainda não está configurado. Contate o administrador.")
    mensagem = EmailMessage()
    mensagem["From"], mensagem["To"], mensagem["Subject"] = remetente, destino, assunto
    mensagem.set_content(corpo)
    try:
        classe = smtplib.SMTP_SSL if modo == "ssl" else smtplib.SMTP
        kwargs = {"context": ssl.create_default_context()} if modo == "ssl" else {}
        with classe(host, int(os.getenv("SMTP_PORT", "465" if modo == "ssl" else "587")), timeout=15, **kwargs) as smtp:
            if modo == "starttls":
                smtp.starttls(context=ssl.create_default_context())
            if os.getenv("SMTP_USER"):
                smtp.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
            smtp.send_message(mensagem)
    except (OSError, smtplib.SMTPException, KeyError, ValueError):
        raise HTTPException(503, "Não foi possível enviar o e-mail. Tente novamente mais tarde.") from None


def limitar(db: Session, chave: str, limite: int = 5):
    digest = hash_token(chave)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:chave, 0))"), {"chave": digest})
    agora = db.scalar(select(func.now()))
    total = db.scalar(select(func.count(TentativaLogin.id)).where(TentativaLogin.chave == digest, TentativaLogin.criado_em > agora - timedelta(minutes=15)))
    if total >= limite:
        raise HTTPException(429, "Muitas solicitações. Aguarde alguns minutos antes de tentar novamente.")
    db.add(TentativaLogin(chave=digest))
    db.flush()


def enviar_token_email(db: Session, usuario: Usuario, finalidade: str, destino: str | None = None):
    destino = destino or usuario.email
    token = secrets.token_urlsafe(32)
    agora = db.scalar(select(func.now()))
    db.execute(update(TokenEmail).where(TokenEmail.usuario_id == usuario.id, TokenEmail.finalidade == finalidade, TokenEmail.usado_em.is_(None)).values(usado_em=agora))
    db.add(TokenEmail(token_hash=hash_token(token), usuario_id=usuario.id, finalidade=finalidade, destino_email=destino, expira_em=agora + timedelta(minutes=30)))
    pagina = "verificar-email" if finalidade == "VERIFICAR" else "redefinir-senha"
    link = f"{PUBLIC_URL}/{pagina}#token={token}"
    enviar_mensagem(destino, "ART X — confirmação de e-mail" if finalidade == "VERIFICAR" else "ART X — recuperação de senha", f"Abra o endereço abaixo para continuar. O link vale por 30 minutos e só pode ser usado uma vez.\n\n{link}\n\nSe você não solicitou esta ação, ignore esta mensagem.")


@router.post("/auth/recuperacao", status_code=202)
def recuperar(dados: SolicitarEmail, db: Session = Depends(get_db)):
    email = str(dados.email).lower()
    limitar(db, "recuperacao:" + email)
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
    if usuario:
        enviar_token_email(db, usuario, "RESET")
    else:
        # A falta de configuracao nao deve revelar se o e-mail existe.
        if not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
            raise HTTPException(503, "O envio de e-mail ainda não está configurado. Contate o administrador.")
    confirmar(db)
    return {"mensagem": "Se houver uma conta para esse e-mail, enviaremos as instruções de recuperação."}


@router.post("/auth/reenviar-verificacao", status_code=202)
def reenviar(dados: SolicitarEmail, db: Session = Depends(get_db)):
    email = str(dados.email).lower()
    limitar(db, "verificacao:" + email)
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email, Usuario.email_verificado.is_(False)))
    if usuario:
        enviar_token_email(db, usuario, "VERIFICAR")
    elif not os.getenv("SMTP_HOST") or not os.getenv("SMTP_FROM"):
        raise HTTPException(503, "O envio de e-mail ainda não está configurado. Contate o administrador.")
    confirmar(db)
    return {"mensagem": "Se a conta precisar de confirmação, enviaremos um novo link."}


def token_valido(db: Session, token: str, finalidade: str):
    registro = db.scalar(select(TokenEmail).where(TokenEmail.token_hash == hash_token(token), TokenEmail.finalidade == finalidade, TokenEmail.usado_em.is_(None), TokenEmail.expira_em > func.now()))
    if registro is None:
        raise HTTPException(400, "Link inválido, expirado ou já utilizado.")
    usuario = db.scalar(select(Usuario).where(Usuario.id == registro.usuario_id).with_for_update())
    if usuario is None:
        raise HTTPException(400, "Link inválido, expirado ou já utilizado.")
    registro = db.scalar(select(TokenEmail).where(TokenEmail.token_hash == hash_token(token), TokenEmail.finalidade == finalidade, TokenEmail.usado_em.is_(None), TokenEmail.expira_em > func.now()).with_for_update().execution_options(populate_existing=True))
    if registro is None:
        raise HTTPException(400, "Link inválido, expirado ou já utilizado.")
    return registro, usuario


@router.post("/auth/verificar")
def verificar_email(dados: ConfirmarToken, db: Session = Depends(get_db)):
    registro, usuario = token_valido(db, dados.token, "VERIFICAR")
    usuario.email = registro.destino_email
    usuario.email_verificado = True
    registro.usado_em = func.now()
    invalidar_sessoes(db, usuario.id)
    confirmar(db)
    return {"mensagem": "E-mail confirmado. Se seu cadastro ainda estiver pendente, aguarde a aprovação do administrador."}


@router.post("/auth/redefinir")
def redefinir(dados: RecuperarSenha, db: Session = Depends(get_db)):
    if dados.nova_senha.get_secret_value() != dados.confirmacao.get_secret_value():
        raise HTTPException(422, "A confirmação da senha não confere.")
    registro, usuario = token_valido(db, dados.token, "RESET")
    if registro.destino_email != usuario.email:
        raise HTTPException(400, "O e-mail da conta foi alterado. Solicite um novo link.")
    usuario.senha_hash = hasher.hash(dados.nova_senha.get_secret_value())
    db.execute(update(TokenEmail).where(TokenEmail.usuario_id == usuario.id, TokenEmail.usado_em.is_(None)).values(usado_em=func.now()))
    invalidar_sessoes(db, usuario.id)
    confirmar(db)
    return {"mensagem": "Senha atualizada. Entre novamente. A aprovação de acesso não foi alterada."}


@router.post("/usuarios/{usuario_id}/aprovacao", response_model=UsuarioPublico)
def aprovar(usuario_id: int, dados: AprovarUsuario, _: Usuario = Depends(administrador), db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.id == usuario_id).with_for_update())
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if usuario.tipo == "ADMIN" and dados.status_acesso != "APROVADO":
        raise HTTPException(409, "O administrador principal não pode ter seu acesso recusado.")
    usuario.status_acesso = dados.status_acesso
    invalidar_sessoes(db, usuario.id)
    confirmar(db)
    return usuario
