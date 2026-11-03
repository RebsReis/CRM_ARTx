from datetime import date
import calendar
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Cliente, ClienteValorMensal


def registrar_valor_inicial(db: Session, cliente: Cliente, *, origem: str, inicio: date) -> ClienteValorMensal:
    registro = ClienteValorMensal(
        cliente_id=cliente.id,
        valor_mensal=cliente.valor_mensal,
        vigencia_inicio=inicio,
        origem=origem,
    )
    db.add(registro)
    return registro


def registrar_reajuste(db: Session, cliente_id: int, valor_mensal: Decimal | float, vigencia_inicio: date | None = None) -> ClienteValorMensal:
    inicio = vigencia_inicio or date.today()
    hoje = date.today()
    if inicio < hoje:
        raise HTTPException(400, "A vigência não pode ser retroativa.")
    cliente = db.scalar(select(Cliente).where(Cliente.id == cliente_id).with_for_update())
    if cliente is None:
        raise HTTPException(404, "Cliente não encontrado.")
    if cliente.status == "INATIVO":
        raise HTTPException(409, "Cliente encerrado não aceita reajustes.")
    if cliente.data_encerramento and inicio >= cliente.data_encerramento:
        raise HTTPException(409, "A vigência ultrapassa o encerramento do contrato.")
    atual = db.scalar(select(ClienteValorMensal).where(
        ClienteValorMensal.cliente_id == cliente_id,
        ClienteValorMensal.vigencia_inicio <= inicio,
        (ClienteValorMensal.vigencia_fim.is_(None) | (ClienteValorMensal.vigencia_fim > inicio)),
    ).with_for_update())
    if atual is not None and atual.vigencia_inicio == inicio:
        raise HTTPException(409, "Já existe uma vigência para esta data.")
    futuro = db.scalar(select(ClienteValorMensal).where(
        ClienteValorMensal.cliente_id == cliente_id,
        ClienteValorMensal.vigencia_inicio > inicio,
    ).order_by(ClienteValorMensal.vigencia_inicio).with_for_update())
    if futuro is not None and inicio < futuro.vigencia_inicio:
        raise HTTPException(409, "Já existe uma vigência futura; a nova data não pode reorganizar a linha do tempo.")
    fim = futuro.vigencia_inicio if futuro else None
    if atual is None and futuro is not None:
        raise HTTPException(409, "Não foi possível determinar a vigência anterior.")
    if atual is not None:
        atual.vigencia_fim = inicio
    registro = ClienteValorMensal(cliente_id=cliente_id, valor_mensal=valor_mensal,
                                  vigencia_inicio=inicio, vigencia_fim=fim, origem="REAJUSTE")
    db.add(registro)
    if inicio <= hoje:
        cliente.valor_mensal = valor_mensal
    return registro


def alterar_valor_na_edicao(db: Session, cliente_id: int, valor_mensal: Decimal | float) -> ClienteValorMensal | None:
    """Valor vindo da edicao do cliente: ignora se nao mudou e corrige a vigencia iniciada hoje."""
    cliente = db.scalar(select(Cliente).where(Cliente.id == cliente_id).with_for_update())
    if cliente is None:
        raise HTTPException(404, "Cliente não encontrado.")
    valor = Decimal(str(valor_mensal)).quantize(Decimal("0.01"))
    if cliente.valor_mensal is not None and valor == Decimal(cliente.valor_mensal).quantize(Decimal("0.01")):
        return None  # A tela sempre envia o valor; sem mudanca nao ha reajuste.
    hoje = date.today()
    de_hoje = db.scalar(select(ClienteValorMensal).where(
        ClienteValorMensal.cliente_id == cliente_id,
        ClienteValorMensal.vigencia_inicio == hoje,
    ).with_for_update())
    if de_hoje is None:
        return registrar_reajuste(db, cliente_id, valor)
    if cliente.status == "INATIVO":
        raise HTTPException(409, "Cliente encerrado não aceita reajustes.")
    # Mesma data: e uma correcao do valor do dia, nao uma nova vigencia.
    de_hoje.valor_mensal = valor
    cliente.valor_mensal = valor
    return de_hoje


def faturamento_recorrente_atual(db: Session) -> Decimal:
    hoje = date.today()
    registros = db.scalars(select(ClienteValorMensal).join(Cliente).where(
        Cliente.status == "ATIVO",
        ClienteValorMensal.vigencia_inicio <= hoje,
        (ClienteValorMensal.vigencia_fim.is_(None) | (ClienteValorMensal.vigencia_fim > hoje)),
    )).all()
    return sum((item.valor_mensal for item in registros), Decimal("0"))


def faturamento_competencia(db: Session, ano: int, mes: int) -> Decimal:
    ultimo_dia = date(ano, mes, calendar.monthrange(ano, mes)[1])
    registros = db.scalars(select(ClienteValorMensal).join(Cliente).where(
        Cliente.data_inicio <= ultimo_dia,
        (Cliente.data_encerramento.is_(None) | (Cliente.data_encerramento >= date(ano, mes, 1))),
        ClienteValorMensal.vigencia_inicio <= ultimo_dia,
        (ClienteValorMensal.vigencia_fim.is_(None) | (ClienteValorMensal.vigencia_fim > ultimo_dia)),
    )).all()
    return sum((item.valor_mensal for item in registros), Decimal("0"))


def novos_faturamentos_competencia(db: Session, ano: int, mes: int) -> Decimal:
    inicio = date(ano, mes, 1)
    registros = db.scalars(select(ClienteValorMensal).join(Cliente).where(
        Cliente.data_inicio >= inicio,
        Cliente.data_inicio < (date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)),
        ClienteValorMensal.origem == "CADASTRO",
    )).all()
    return sum((item.valor_mensal for item in registros), Decimal("0"))
