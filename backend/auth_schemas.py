from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DadosPessoais(Entrada):
    nome: str = Field(min_length=1, max_length=150)
    email: EmailStr = Field(max_length=150)

    @field_validator("nome")
    @classmethod
    def nome_valido(cls, value):
        if not value.strip():
            raise ValueError("Informe o nome.")
        return value.strip()

    @field_validator("email")
    @classmethod
    def email_normalizado(cls, value):
        return str(value).lower()


class CriarUsuario(DadosPessoais):
    senha: SecretStr = Field(min_length=8, max_length=128)
    tipo: Literal["ADMIN", "USUARIO"] = "USUARIO"


class AtualizarConta(DadosPessoais):
    senha_atual: SecretStr | None = Field(default=None, max_length=128)


class EditarUsuario(DadosPessoais):
    tipo: Literal["ADMIN", "USUARIO"]
    ativo: bool


class Login(Entrada):
    email: EmailStr = Field(max_length=150)
    senha: SecretStr = Field(min_length=1, max_length=128)


class RedefinirSenha(Entrada):
    nova_senha: SecretStr = Field(min_length=8, max_length=128)


class AlterarSenha(RedefinirSenha):
    senha_atual: SecretStr = Field(min_length=1, max_length=128)
    confirmacao: SecretStr = Field(min_length=8, max_length=128)


class UsuarioPublico(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nome: str
    email: str
    tipo: Literal["ADMIN", "USUARIO"]
    ativo: bool
    criado_em: datetime
    status_acesso: Literal["PENDENTE", "APROVADO", "RECUSADO"]
    email_verificado: bool


class SolicitarEmail(Entrada):
    email: EmailStr = Field(max_length=150)


class ConfirmarToken(Entrada):
    token: str = Field(min_length=32, max_length=128)


class RecuperarSenha(ConfirmarToken, RedefinirSenha):
    confirmacao: SecretStr = Field(min_length=8, max_length=128)


class AprovarUsuario(Entrada):
    status_acesso: Literal["APROVADO", "RECUSADO"]
