"""Representa dados recebidos ou enviados pela API-Utiliza Pydantic-Define como os dados são validados"""

from decimal import Decimal
from typing import Literal
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LeadCreate(BaseModel): #indica que estamos criando um modelo de validação de dados

    nome_empresa: str = Field( #permite estabelecer regras. Por exemplo:
        min_length=1,
        max_length=150
    )

    nicho: str | None = Field( #significa que o nicho é opcional.
        default=None,
        max_length=100
    )

    telefone: str | None = Field(
        default=None,
        max_length=30
    )

    email: str | None = Field(
        default=None,
        max_length=150
    )
#garante que o usuário só consiga enviar uma das quatro fases permitidas pelo CRM.
    fase: Literal[
        "PROSPECTAR",
        "FOLLOW_UP",
        "REUNIAO_MARCADA",
        "REMARKETING_FUTURO"
    ] = "PROSPECTAR"

    observacao: str | None = None
class LeadFaseUpdate(BaseModel):
    fase: Literal[
        "PROSPECTAR",
        "FOLLOW_UP",
        "REUNIAO_MARCADA",
        "REMARKETING_FUTURO"
    ]




class ClienteCreate(BaseModel):
    nome_empresa: str = Field(min_length=1, max_length=150)
    nicho: str | None = None
    telefone: str | None = None
    email: str | None = None

    valor_mensal: Decimal = Field(ge=0)

    data_inicio: date | None = None


class ProjetoCreate(BaseModel):
    cliente_id: int
    nome_projeto: str = Field(min_length=1, max_length=200)
    prazo: date | None = None
    prioridade: Literal[
        "BAIXA", "MEDIA", "ALTA", "URGENTE"
    ] = "MEDIA"
    status: Literal[
        "PENDENTE", "EM_ANDAMENTO", "FINALIZADA"
    ] = "PENDENTE"
    observacao: str | None = None

class ProjetoStatusUpdate(BaseModel):
    status: Literal[
        "PENDENTE",
        "EM_ANDAMENTO",
        "FINALIZADA"
    ]

    @field_validator("status", mode="before")
    @classmethod
    def normalizar_status_concluido(cls, valor):
        # Compatibilidade com abas abertas antes da correção do Kanban.
        return "FINALIZADA" if valor == "CONCLUIDO" else valor

class ChecklistItemCreate(BaseModel):
    descricao: str
    ordem: int = 0

class ChecklistStatusUpdate(BaseModel):
    concluido: bool




class ChecklistUpdate(BaseModel):
    descricao: Optional[str] = None
    ordem: Optional[int] = None

class ProjetoUpdate(BaseModel):
    nome_projeto: Optional[str] = None
    prazo: Optional[date] = None
    prioridade: Optional[str] = None
    observacao: Optional[str] = None

class MetaCreate(BaseModel):
    ano: int = Field(ge=2020, le=2100)
    mes: int = Field(ge=1, le=12)

    meta_prospeccoes: int = Field(ge=0)
    meta_reunioes: int = Field(ge=0)
    meta_faturamento: float = Field(ge=0)



class ReuniaoCreate(BaseModel):
    lead_id: int
    data_reuniao: datetime
    observacao: Optional[str] = None


class ClienteReajusteCreate(BaseModel):
    valor_mensal: float = Field(ge=0)
    vigencia_inicio: date | None = None
