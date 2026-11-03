from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, Identity, Index, String, text
from models import Base


class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(BigInteger, Identity(always=True), primary_key=True)
    nome = Column(String(150), nullable=False)
    email = Column(String(150), nullable=False, unique=True)
    senha_hash = Column(String(255), nullable=True)
    status_acesso = Column(String(20), nullable=False, server_default="APROVADO")
    email_verificado = Column(Boolean, nullable=False, server_default=text("true"))
    tipo = Column(String(20), nullable=False, server_default="USUARIO")
    ativo = Column(Boolean, nullable=False, server_default=text("true"))
    criado_em = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    atualizado_em = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        CheckConstraint("tipo IN ('ADMIN', 'USUARIO')", name="usuarios_tipo_check"),
        CheckConstraint("tipo <> 'ADMIN' OR ativo", name="usuarios_admin_ativo"),
        CheckConstraint("status_acesso IN ('PENDENTE', 'APROVADO', 'RECUSADO')", name="usuarios_status_acesso_check"),
        Index("usuarios_um_admin", tipo, unique=True, postgresql_where=text("tipo = 'ADMIN'")),
    )


class SessaoUsuario(Base):
    __tablename__ = "sessoes_usuario"
    token_hash = Column(String(64), primary_key=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class TentativaLogin(Base):
    __tablename__ = "tentativas_login"
    id = Column(BigInteger, Identity(always=True), primary_key=True)
    chave = Column(String(64), nullable=False, index=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class IdentidadeGoogle(Base):
    __tablename__ = "identidades_google"
    sub = Column(String(255), primary_key=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, unique=True)
    email_google = Column(String(150), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=text("CURRENT_TIMESTAMP"))


class TokenEmail(Base):
    __tablename__ = "tokens_email"
    token_hash = Column(String(64), primary_key=True)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    finalidade = Column(String(20), nullable=False)
    destino_email = Column(String(150), nullable=False)
    expira_em = Column(DateTime(timezone=True), nullable=False)
    usado_em = Column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("finalidade IN ('VERIFICAR', 'RESET')", name="tokens_email_finalidade_check"),)

class FluxoGoogle(Base):
    __tablename__ = "fluxos_google"
    state_hash = Column(String(64), primary_key=True)
    browser_hash = Column(String(64), nullable=False)
    nonce = Column(String(64), nullable=False)
    verifier = Column(String(128), nullable=False)
    usuario_id = Column(BigInteger, ForeignKey("usuarios.id", ondelete="CASCADE"))
    sessao_hash = Column(String(64))
    expira_em = Column(DateTime(timezone=True), nullable=False)

