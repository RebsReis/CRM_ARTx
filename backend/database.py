from pathlib import Path

from dotenv import load_dotenv #Ele carrega as variáveis existentes no nosso .env.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from db_config import build_database_url, engine_options


load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

DATABASE_URL = build_database_url()


engine = create_engine(DATABASE_URL, **engine_options(DATABASE_URL))


SessionLocal = sessionmaker( #será nossa unidade de trabalho com o banco.
    bind=engine,
    autoflush=False,
    autocommit=False
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



