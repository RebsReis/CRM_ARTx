"""Sem conexao automatica; alvo de migracao separado do runtime do CRM."""
from pathlib import Path
import sys

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
from db_config import build_migration_url, engine_options, validate_migration_target
from schema_guard import bootstrap_statements, validate_operation
from models import Base
import auth_models  # Registra todas as tabelas; nao importa database/main nem conecta.

config = context.config
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Preserva objetos legados que nao aparecem nos modelos. Revisao manual obrigatoria.
    return not (reflected and compare_to is None)


def process_revision_directives(ctx, revision, directives):
    # Autogenerate nunca e autorizacao para apagar tabelas/colunas.
    def validate(operation):
        if operation.__class__.__name__ in {"DropTableOp", "DropColumnOp"}:
            raise RuntimeError("Autogenerate produziu remocao destrutiva; revisar manualmente.")
        for child in getattr(operation, "ops", ()):
            validate(child)
    for directive in directives:
        validate(directive.upgrade_ops)


def command_name():
    cmd = getattr(getattr(config, "cmd_opts", None), "cmd", None)
    return getattr(cmd[0], "__name__", "") if cmd else ""


def run_migrations_offline():
    # Somente emissao SQL. Tambem bloqueada enquanto a baseline estiver incompleta.
    bootstrap_statements()
    context.configure(dialect_name="postgresql", target_metadata=target_metadata,
                      literal_binds=True, version_table_schema="public")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    mode = validate_operation(command_name(), context.get_x_argument(as_dictionary=True))
    load_dotenv(BACKEND.parent / ".env", override=False)
    url = build_migration_url()  # Nunca recorre a DATABASE_URL/DB_* da API.
    validate_migration_target(url)
    engine = create_engine(url, **engine_options(url, migration=True))
    try:
        with engine.connect() as connection:
            # Mesmo endereco PostgreSQL nao significa mesmo schema. Alvo fixo public.
            with connection.begin():
                connection.execute(text("SET LOCAL search_path TO public"))
                connection.execute(text("SET LOCAL lock_timeout TO '5s'"))
                if mode == "new":
                    occupied = connection.scalar(text("""
                        SELECT EXISTS (
                            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                            WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S','f')
                        ) OR EXISTS (
                            SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
                            WHERE n.nspname='public'
                        )
                    """))
                    if occupied:
                        raise RuntimeError("Inicializacao recusada: schema public nao esta vazio.")
                elif mode == "existing" and command_name() != "stamp":
                    if connection.scalar(text("SELECT to_regclass('public.alembic_version')")) is None:
                        raise RuntimeError("Banco sem versao: comparar esquema antes de qualquer adocao por stamp.")
                context.configure(
                    connection=connection, target_metadata=target_metadata,
                    version_table_schema="public", compare_type=True,
                    include_object=include_object,
                    process_revision_directives=process_revision_directives,
                )
                with context.begin_transaction():
                    context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
