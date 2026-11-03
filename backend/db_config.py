"""Configuracao pura: nao le arquivos, nao cria engine e nao conecta ao banco."""
import os
from collections.abc import Mapping

from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

MIGRATION_TARGET_DATABASE = "artx_crm_teste_baseline"
MIGRATION_TARGET_HOSTS = frozenset({"localhost", "127.0.0.1"})


def _integer(env: Mapping[str, str], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(env.get(key, str(default)))
    except (ValueError, TypeError):
        raise ValueError(f"{key} deve ser um numero inteiro valido.") from None
    if not minimum <= value <= maximum:
        raise ValueError(f"{key} esta fora do intervalo permitido.")
    return value


def is_neon(url: URL) -> bool:
    return (url.host or "").lower().rstrip(".").endswith(".neon.tech")


def build_database_url(environ: Mapping[str, str] | None = None) -> URL:
    env = os.environ if environ is None else environ
    raw = env.get("DATABASE_URL", "").strip()
    if raw:
        try:
            url = make_url(raw)
            if url.drivername not in {"postgres", "postgresql", "postgresql+psycopg"}:
                raise ValueError
            url = url.set(drivername="postgresql+psycopg")
            if not url.host or not url.database or not url.username:
                raise ValueError
            if url.port is not None and not 1 <= url.port <= 65535:
                raise ValueError
        except Exception:
            # Nunca incluir a URL, credenciais ou a excecao do parser na mensagem.
            raise ValueError("DATABASE_URL deve ser uma URL PostgreSQL valida com host, banco e usuario.") from None
    else:
        for key in ("DB_HOST", "DB_NAME", "DB_USER"):
            if not env.get(key, "").strip():
                raise ValueError(f"Configure DATABASE_URL ou {key}.")
        if "DB_PASSWORD" not in env:
            raise ValueError("Configure DATABASE_URL ou DB_PASSWORD.")
        # URL.create recebe a senha literal: @, %, /, # e espacos nao viram delimitadores.
        url = URL.create(
            "postgresql+psycopg", username=env["DB_USER"], password=env["DB_PASSWORD"],
            host=env["DB_HOST"], port=_integer(env, "DB_PORT", 5432, 1, 65535),
            database=env["DB_NAME"],
        )
    query = dict(url.query)
    for key, variable in (("sslmode", "DB_SSLMODE"), ("sslrootcert", "DB_SSLROOTCERT"),
                          ("channel_binding", "DB_CHANNEL_BINDING")):
        configured = env.get(variable, "").strip()
        if configured:
            if key in query and query[key] != configured:
                raise ValueError(f"Configuracao conflitante entre DATABASE_URL e {variable}.")
            query[key] = configured
    mode = query.get("sslmode")
    if mode is not None and mode not in {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}:
        raise ValueError("sslmode invalido na configuracao PostgreSQL.")
    if is_neon(url):
        query.setdefault("sslmode", "verify-full")
        if query["sslmode"] not in {"require", "verify-ca", "verify-full"}:
            raise ValueError("Conexoes Neon exigem TLS; use preferencialmente sslmode=verify-full.")
        if query["sslmode"] == "verify-full":
            query.setdefault("sslrootcert", "system")
        query.setdefault("channel_binding", "require")
    if query.get("channel_binding") not in {None, "disable", "prefer", "require"}:
        raise ValueError("channel_binding invalido na configuracao PostgreSQL.")
    return url.set(query=query)


def engine_options(url: URL, environ: Mapping[str, str] | None = None, *, migration: bool = False) -> dict:
    env = os.environ if environ is None else environ
    connect_args = {"connect_timeout": _integer(env, "DB_CONNECT_TIMEOUT", 10, 1, 300)}
    threshold = env.get("DB_PREPARE_THRESHOLD", "").strip().lower()
    if migration or threshold == "none" or (not threshold and is_neon(url) and "-pooler" in (url.host or "").lower().split(".")[0]):
        connect_args["prepare_threshold"] = None
    elif threshold:
        connect_args["prepare_threshold"] = _integer(env, "DB_PREPARE_THRESHOLD", 5, 0, 100000)
    options = {"pool_pre_ping": True, "connect_args": connect_args, "hide_parameters": True}
    mode = env.get("DB_POOL_MODE", "queue").strip().lower()
    if migration or mode == "null":
        options["poolclass"] = NullPool
    elif mode == "queue":
        options.update(
            pool_size=_integer(env, "DB_POOL_SIZE", 5, 1, 100),
            max_overflow=_integer(env, "DB_MAX_OVERFLOW", 10, 0, 100),
            pool_recycle=_integer(env, "DB_POOL_RECYCLE", -1, -1, 86400),
        )
    else:
        raise ValueError("DB_POOL_MODE deve ser queue ou null.")
    return options


def build_migration_url(environ: Mapping[str, str] | None = None) -> URL:
    env = os.environ if environ is None else environ
    raw = env.get("MIGRATION_DATABASE_URL", "").strip()
    if not raw:
        raise ValueError("MIGRATION_DATABASE_URL e obrigatoria; migracoes nunca reutilizam DB_* automaticamente.")
    url = build_database_url({**env, "DATABASE_URL": raw})
    validate_migration_target(url)
    if "-pooler" in (url.host or "").lower().split(".")[0]:
        raise ValueError("Migracoes exigem conexao direta, sem endpoint -pooler.")
    return url


def validate_migration_target(url: URL) -> URL:
    """Reject every migration target except the local isolated test database."""
    if url.drivername != "postgresql+psycopg":
        raise ValueError("MIGRATION_DATABASE_URL deve usar o driver PostgreSQL psycopg.")
    if (url.host or "").lower() not in MIGRATION_TARGET_HOSTS:
        raise ValueError("Migrações só podem usar um host PostgreSQL local autorizado.")
    if url.database != MIGRATION_TARGET_DATABASE:
        raise ValueError("Migrações só podem usar o banco de testes autorizado.")
    return url
