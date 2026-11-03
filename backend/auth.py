import hashlib
import os
import secrets
from datetime import timedelta

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from auth_models import SessaoUsuario, TentativaLogin, TokenEmail, Usuario
from auth_schemas import AlterarSenha, AtualizarConta, CriarUsuario, DadosPessoais, EditarUsuario, Login, RedefinirSenha, UsuarioPublico

COOKIE = "artx_session"
ORIGINS = frozenset(x.strip().rstrip("/") for x in os.getenv("APP_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","))
SECURE_COOKIE = os.getenv("AUTH_COOKIE_SECURE", "false").lower() == "true"
hasher = PasswordHasher(type=Type.ID)
dummy_hash = hasher.hash(secrets.token_urlsafe(32))
router = APIRouter(tags=["Autenticacao e usuarios"])


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verificar_senha(hash_salvo: str, senha: str) -> bool:
    # Hashes desconhecidos nunca sao interpretados como senhas em texto puro.
    if not hash_salvo:
        return False
    try:
        return hasher.verify(hash_salvo, senha)
    except (VerificationError, InvalidHashError):
        return False


def usuario_atual(request: Request, db: Session = Depends(get_db)) -> Usuario:
    token = request.cookies.get(COOKIE, "")
    if not token or len(token) > 256:
        raise HTTPException(401, "Sessão ausente ou expirada.")
    usuario = db.scalar(select(Usuario).join(SessaoUsuario, SessaoUsuario.usuario_id == Usuario.id).where(
        SessaoUsuario.token_hash == hash_token(token), SessaoUsuario.expira_em > func.now(), Usuario.ativo.is_(True),
        Usuario.status_acesso == "APROVADO", Usuario.email_verificado.is_(True),
    ))
    if usuario is None:
        raise HTTPException(401, "Sessão ausente ou expirada.")
    return usuario


def administrador(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
    if usuario.tipo != "ADMIN":
        raise HTTPException(403, "Acesso restrito ao administrador.")
    return usuario


def proteger_crm(request: Request, db: Session = Depends(get_db)):
    if request.method == "OPTIONS":
        return
    if request.method not in {"GET", "HEAD"}:
        if request.headers.get("origin", "").rstrip("/") not in ORIGINS:
            raise HTTPException(403, "Origem da solicitação não autorizada.")
    if request.url.path in {"/", "/auth/login", "/auth/logout", "/auth/recuperacao", "/auth/redefinir", "/auth/verificar", "/auth/reenviar-verificacao"}:
        return
    usuario_atual(request, db)


def invalidar_sessoes(db: Session, usuario_id: int):
    db.execute(delete(SessaoUsuario).where(SessaoUsuario.usuario_id == usuario_id))


def confirmar(db: Session):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "E-mail já cadastrado ou operação incompatível com o administrador principal.")


def emitir_sessao(db: Session, usuario: Usuario, request: Request, response: Response):
    token = secrets.token_urlsafe(32)
    token_antigo = request.cookies.get(COOKIE)
    if token_antigo:
        db.execute(delete(SessaoUsuario).where(SessaoUsuario.token_hash == hash_token(token_antigo)))
    agora = db.scalar(select(func.now()))
    db.add(SessaoUsuario(token_hash=hash_token(token), usuario_id=usuario.id, expira_em=agora + timedelta(hours=8)))
    confirmar(db)
    response.set_cookie(COOKIE, token, max_age=8 * 3600, httponly=True, secure=SECURE_COOKIE, samesite="lax", path="/")


@router.post("/auth/login", response_model=UsuarioPublico)
def login(dados: Login, request: Request, response: Response, db: Session = Depends(get_db)):
    email = str(dados.email).lower()
    chave = hash_token(email)
    # Limite persistente entre processos; serializa tentativas da mesma conta.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:chave, 0))"), {"chave": chave})
    agora = db.scalar(select(func.now()))
    tentativas = db.scalar(select(func.count(TentativaLogin.id)).where(TentativaLogin.chave == chave, TentativaLogin.criado_em > agora - timedelta(minutes=15)))
    if tentativas >= 10:
        raise HTTPException(429, "Muitas tentativas. Tente novamente em alguns minutos.")
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email).with_for_update())
    valido = verificar_senha(usuario.senha_hash if usuario else dummy_hash, dados.senha.get_secret_value())
    if not usuario or not valido or not usuario.ativo:
        db.add(TentativaLogin(chave=chave))
        db.commit()
        raise HTTPException(401, "E-mail ou senha inválidos.")
    if usuario.status_acesso == "PENDENTE":
        raise HTTPException(403, "Cadastro pendente de aprovação. Confirme também seu e-mail para acessar o CRM.")
    if usuario.status_acesso == "RECUSADO":
        raise HTTPException(403, "Cadastro recusado. Entre em contato com o administrador.")
    if not usuario.email_verificado:
        raise HTTPException(403, "Confirme seu e-mail antes de acessar o CRM.")
    if hasher.check_needs_rehash(usuario.senha_hash):
        usuario.senha_hash = hasher.hash(dados.senha.get_secret_value())
    db.execute(delete(TentativaLogin).where(TentativaLogin.chave == chave))
    emitir_sessao(db, usuario, request, response)
    return usuario


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(SessaoUsuario).where(SessaoUsuario.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(COOKIE, path="/", secure=SECURE_COOKIE, httponly=True, samesite="lax")


@router.get("/auth/me", response_model=UsuarioPublico)
def minha_conta(usuario: Usuario = Depends(usuario_atual)):
    return usuario


@router.patch("/auth/me", response_model=UsuarioPublico)
def editar_minha_conta(dados: AtualizarConta, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    db.refresh(usuario, with_for_update=True)
    usuario.nome = dados.nome
    if str(dados.email) != usuario.email:
        if not dados.senha_atual or not verificar_senha(usuario.senha_hash, dados.senha_atual.get_secret_value()):
            raise HTTPException(400, "Confirme sua senha atual para solicitar uma alteração de e-mail.")
        from auth_public import enviar_token_email
        enviar_token_email(db, usuario, "VERIFICAR", str(dados.email))
    usuario.atualizado_em = func.localtimestamp()
    confirmar(db)
    return usuario


@router.post("/auth/senha", status_code=204)
def alterar_minha_senha(dados: AlterarSenha, response: Response, usuario: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    db.refresh(usuario, with_for_update=True)
    if dados.nova_senha.get_secret_value() != dados.confirmacao.get_secret_value():
        raise HTTPException(422, "A confirmação da senha não confere.")
    if not verificar_senha(usuario.senha_hash, dados.senha_atual.get_secret_value()):
        raise HTTPException(400, "Senha atual inválida.")
    usuario.senha_hash = hasher.hash(dados.nova_senha.get_secret_value())
    db.query(TokenEmail).filter(TokenEmail.usuario_id == usuario.id, TokenEmail.usado_em.is_(None)).update({TokenEmail.usado_em: func.now()}, synchronize_session=False)
    usuario.atualizado_em = func.localtimestamp()
    invalidar_sessoes(db, usuario.id)
    confirmar(db)
    response.delete_cookie(COOKIE, path="/", secure=SECURE_COOKIE, httponly=True, samesite="lax")


@router.get("/usuarios", response_model=list[UsuarioPublico])
def listar_usuarios(_: Usuario = Depends(administrador), db: Session = Depends(get_db)):
    return db.scalars(select(Usuario).order_by(Usuario.id)).all()


@router.post("/usuarios", response_model=UsuarioPublico, status_code=201)
def criar_usuario(dados: CriarUsuario, _: Usuario = Depends(administrador), db: Session = Depends(get_db)):
    usuario = Usuario(nome=dados.nome, email=str(dados.email), senha_hash=hasher.hash(dados.senha.get_secret_value()), tipo=dados.tipo, ativo=True)
    db.add(usuario)
    confirmar(db)
    return usuario


@router.put("/usuarios/{usuario_id}", response_model=UsuarioPublico)
def editar_usuario(usuario_id: int, dados: EditarUsuario, _: Usuario = Depends(administrador), db: Session = Depends(get_db)):
    usuario = db.scalar(select(Usuario).where(Usuario.id == usuario_id).with_for_update())
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if usuario.tipo == "ADMIN" and (dados.tipo != "ADMIN" or not dados.ativo):
        raise HTTPException(409, "O administrador principal não pode ser desativado ou perder o perfil.")
    mudou_acesso = usuario.tipo != dados.tipo or usuario.ativo != dados.ativo
    if str(dados.email) != usuario.email:
        from auth_public import enviar_token_email
        enviar_token_email(db, usuario, "VERIFICAR", str(dados.email))
    usuario.nome, usuario.tipo, usuario.ativo = dados.nome, dados.tipo, dados.ativo
    usuario.atualizado_em = func.localtimestamp()
    if mudou_acesso:
        invalidar_sessoes(db, usuario.id)
    confirmar(db)
    return usuario


@router.post("/usuarios/{usuario_id}/senha", status_code=204)
def redefinir_senha(usuario_id: int, dados: RedefinirSenha, admin: Usuario = Depends(administrador), db: Session = Depends(get_db)):
    if usuario_id == admin.id:
        raise HTTPException(400, "Para alterar sua senha, utilize Minha conta e informe a senha atual.")
    usuario = db.scalar(select(Usuario).where(Usuario.id == usuario_id).with_for_update())
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado.")
    usuario.senha_hash = hasher.hash(dados.nova_senha.get_secret_value())
    db.query(TokenEmail).filter(TokenEmail.usuario_id == usuario.id, TokenEmail.usado_em.is_(None)).update({TokenEmail.usado_em: func.now()}, synchronize_session=False)
    usuario.atualizado_em = func.localtimestamp()
    invalidar_sessoes(db, usuario.id)
    confirmar(db)
