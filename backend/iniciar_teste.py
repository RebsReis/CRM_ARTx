"""Sobe a API local no banco de TESTE (artx_crm_teste_baseline), com as credenciais do .env.

Uso, na pasta artx-crm:
    .venv\\stage2-validation\\Scripts\\python.exe backend\\iniciar_teste.py
Nao imprime a senha. Para usar o banco real, rode o uvicorn normalmente (ver AMBIENTE.md).
"""
import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from dotenv import load_dotenv
from db_config import build_database_url

load_dotenv(BACKEND.parent / ".env", override=False)
os.environ.pop("DATABASE_URL", None)
url = build_database_url().set(database="artx_crm_teste_baseline")
os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
print(f"API no banco de teste: {url.host}/{url.database}", flush=True)

import uvicorn

uvicorn.run("main:app", host="127.0.0.1", port=8000)
