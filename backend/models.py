"""Representa tabelas do PostgreSQL-Utiliza SQLAlchemy-Define como os dados são persistidos"""

from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, Index
from sqlalchemy import BigInteger, Column, Date, ForeignKey, Integer, Numeric, String, Text, DateTime,Identity, text,Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime,date
from sqlalchemy import BigInteger, String, Text, DateTime, Identity, text



class Base(DeclarativeBase): #classe base que o SQLAlchemy utiliza para registrar nossos modelos
    pass


class Lead(Base): #Informa que a classe Python Lead representa a tabela leads que já existe no PostgreSQL.
    __tablename__ = "leads" 

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
)

    nome_empresa: Mapped[str] = mapped_column( #Significa que nome_empresa é um atributo Python associado a uma coluna do banco, cujo tipo é VARCHAR(150).
        String(150)
    )

    nicho: Mapped[str | None] = mapped_column(
        String(100)
    )

    telefone: Mapped[str | None] = mapped_column(
        String(30)
    )

    email: Mapped[str | None] = mapped_column(
        String(150)
    )

    fase: Mapped[str] = mapped_column(
        String(30)
    )

    observacao: Mapped[str | None] = mapped_column(
        Text
    )

    criado_em: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
)
    

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
)
    prospectado_em = Column(DateTime, nullable=True)
    # Leads excluidos/convertidos permanecem como referencia historica.
    arquivado_em = Column(DateTime, nullable=True)
    __table_args__ = (CheckConstraint("fase IN ('PROSPECTAR', 'FOLLOW_UP', 'REUNIAO_MARCADA', 'REMARKETING_FUTURO')", name="leads_fase_check"),)
#representa as movimentações que aconteceram ao longo do tempo.
class HistoricoLead(Base):
    __tablename__ = "historico_leads"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
    )

    lead_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("leads.id", ondelete="CASCADE")
    )

    fase_anterior: Mapped[str | None] = mapped_column(
        String(30)
    )

    fase_nova: Mapped[str] = mapped_column(
        String(30)
    )

    movimentado_em: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
    )

    lead_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("leads.id", ondelete="SET NULL"),
        unique=True,
        nullable=True
    )

    __table_args__ = (
        CheckConstraint("data_encerramento IS NULL OR data_encerramento >= data_inicio", name="chk_datas_cliente"),
        CheckConstraint("status IN ('ATIVO', 'INATIVO')", name="clientes_status_check"),
        CheckConstraint("valor_mensal >= 0", name="clientes_valor_mensal_check"),
    )

    nome_empresa: Mapped[str] = mapped_column(String(150))
    nicho: Mapped[str | None] = mapped_column(String(100))
    telefone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(150))
    valor_mensal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    data_inicio: Mapped[date] = mapped_column(Date, server_default=text("CURRENT_DATE"))
    data_encerramento: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'ATIVO'"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, server_default=text("CURRENT_TIMESTAMP"))


class ClienteValorMensal(Base):
    __tablename__ = "cliente_valores_mensais"
    id = Column(BigInteger, Identity(always=True), primary_key=True)
    cliente_id = Column(BigInteger, ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True)
    valor_mensal = Column(Numeric(12, 2), nullable=False)
    vigencia_inicio = Column(Date, nullable=False)
    vigencia_fim = Column(Date, nullable=True)
    origem = Column(String(30), nullable=False)
    criado_em = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (
        CheckConstraint("valor_mensal >= 0", name="cliente_valores_mensais_valor_check"),
        CheckConstraint("vigencia_fim IS NULL OR vigencia_fim > vigencia_inicio", name="cliente_valores_mensais_datas_check"),
        CheckConstraint("origem IN ('CADASTRO', 'REAJUSTE', 'MIGRACAO_SNAPSHOT')", name="cliente_valores_mensais_origem_check"),
        Index("ix_cliente_valores_mensais_cliente_inicio", "cliente_id", "vigencia_inicio"),
        ExcludeConstraint(
            ("cliente_id", "="),
            (text("daterange(vigencia_inicio, COALESCE(vigencia_fim, 'infinity'::date), '[)')"), "&&"),
            name="cliente_valores_mensais_sem_sobreposicao",
            using="gist",
        ),
    )

class Projeto(Base):
    __tablename__ = "projetos"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
    )

    cliente_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("clientes.id"),
        nullable=False
    )

    nome_projeto: Mapped[str] = mapped_column(
        String(200),
        nullable=False
    )

    prazo: Mapped[date | None] = mapped_column(
        Date
    )

    prioridade: Mapped[str] = mapped_column(
        String(20),
        server_default=text("'MEDIA'")
    )

    status: Mapped[str] = mapped_column(
        String(30),
        server_default=text("'PENDENTE'")
    )

    observacao: Mapped[str | None] = mapped_column(
        Text
    )

    criado_em = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP")
    )
    __table_args__ = (
        CheckConstraint("prioridade IN ('BAIXA', 'MEDIA', 'ALTA', 'URGENTE')", name="projetos_prioridade_check"),
        CheckConstraint("status IN ('PENDENTE', 'EM_ANDAMENTO', 'FINALIZADA')", name="projetos_status_check"),
    )


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    projeto_id = Column(BigInteger, ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False)
    descricao = Column(String(255), nullable=False)
    concluido = Column(Boolean, nullable=False, server_default=text("false"))
    ordem = Column(Integer, nullable=False, server_default=text("0"))

    criado_em = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP")
    )

    concluido_em = Column(DateTime, nullable=True)


class Meta(Base):
    __tablename__ = "metas"

    id = Column(BigInteger, Identity(always=True), primary_key=True)

    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)

    meta_prospeccoes = Column(
        Integer, nullable=False, default=0
    )

    meta_reunioes = Column(
        Integer, nullable=False, default=0
    )

    meta_faturamento = Column(
        Numeric(12, 2), nullable=False, server_default=text("0")
    )

    criado_em = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    atualizado_em = Column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        UniqueConstraint("ano", "mes", name="uq_meta_mes"),
        CheckConstraint("mes BETWEEN 1 AND 12", name="metas_mes_check"),
        CheckConstraint("meta_prospeccoes >= 0", name="metas_meta_prospeccoes_check"),
        CheckConstraint("meta_reunioes >= 0", name="metas_meta_reunioes_check"),
        CheckConstraint("meta_faturamento >= 0", name="metas_meta_faturamento_check"),
    )

class Reuniao(Base):
    __tablename__ = "reunioes"

    id = Column(BigInteger, Identity(always=True), primary_key=True)
    lead_id = Column(BigInteger, ForeignKey("leads.id"), nullable=False)

    data_reuniao = Column(DateTime, nullable=False)

    status = Column(String(20), nullable=False, server_default=text("'AGENDADA'"))

    observacao = Column(Text)

    criado_em = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        CheckConstraint("status IN ('AGENDADA', 'REALIZADA', 'CANCELADA')", name="reunioes_status_check"),
    )
