"""Travas de preparacao das migracoes; nenhuma conexao ou operacao de banco."""
import hashlib
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "alembic" / "sql"
BASELINE_REVISION = "20261027_0001"


def bootstrap_statements() -> tuple[str, str]:
    manifest = json.loads((ASSETS / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "confirmed":
        raise RuntimeError(
            "Baseline bloqueada: recuperar e revisar as definicoes reais de funcoes/triggers "
            "e as divergencias descritas em BANCO_PRODUCAO.md antes de qualquer aplicacao."
        )
    statements = []
    for filename in ("initial_schema.sql", "history_triggers.sql"):
        expected = manifest.get("sha256", {}).get(filename)
        path = ASSETS / filename
        if not expected or not path.is_file():
            raise RuntimeError("Baseline incompleta: falta um artefato SQL revisado.")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected:
            raise RuntimeError("Artefato da baseline foi alterado; revisar a versao antes de aplicar.")
        statements.append(content.decode("utf-8"))
    return tuple(statements)


def validate_operation(command: str, arguments: dict[str, str]) -> str:
    if command == "downgrade":
        raise RuntimeError("Downgrade bloqueado: exige plano especifico de restauracao e autorizacao.")
    if arguments.get("allow_database_access") != "yes":
        raise RuntimeError("Acesso ao banco bloqueado. Esta preparacao nao autoriza nenhuma conexao.")
    mode = arguments.get("mode")
    if mode == "inspect" and command == "current":
        return mode
    if mode == "new" and command == "upgrade":
        bootstrap_statements()  # Falha ANTES de criar engine ou tabela de versao.
        return mode
    if mode == "existing" and command in {"upgrade", "stamp", "revision", "check"}:
        if arguments.get("schema_reviewed") != "yes":
            raise RuntimeError("Banco existente exige comparacao do esquema e backup restauravel revisados.")
        bootstrap_statements()
        return mode
    raise RuntimeError("Operacao/modo nao autorizado. Leia BANCO_PRODUCAO.md.")
