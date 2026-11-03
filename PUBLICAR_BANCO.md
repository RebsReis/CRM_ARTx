# Banco de produção novo (Neon) — passo a passo

Decisão de 03/11/2026: a produção começa com um banco **novo e vazio**. Os dados
locais (`CRM_artX`) não são copiados; leads, clientes e projetos são recadastrados
pelo CRM. O banco local continua intacto.

Os passos 1 e 2 são feitos por você no site do Neon. Os passos 3 a 5 rodam no
PowerShell, na pasta do projeto. Nenhuma senha deve ser salva em arquivo do projeto.

## 1. Criar o banco no Neon

1. Crie uma conta em neon.tech e um projeto (região sugerida: São Paulo, `sa-east-1`).
2. Crie um banco chamado `artx_crm` (ou use o padrão `neondb`).
3. Em **Connect**, copie duas URLs de conexão:
   - **Direta** (sem `-pooler` no endereço): usada só nos passos 3 e 4.
   - **Pooled** (com `-pooler`): usada pela API no Render (passo 6).

## 2. Anotar o alvo autorizado

O alvo é `host/banco`, sem usuário nem senha. Exemplo:
`ep-nome-123456.sa-east-1.aws.neon.tech/artx_crm`

Sem essa liberação, as migrações e o bootstrap continuam aceitando apenas o banco
de testes local. Ela nunca aceita um PostgreSQL local e exige TLS.

## 3. Criar as tabelas (migrações)

```powershell
py -3.13 -m venv .venv-migracoes
.venv-migracoes\Scripts\python.exe -m pip install -r backend\requirements-migrations.txt

$env:MIGRATION_PRODUCTION_TARGET = "ep-nome-123456.sa-east-1.aws.neon.tech/artx_crm"
$env:MIGRATION_DATABASE_URL = Read-Host "Cole a URL DIRETA do Neon"
.venv-migracoes\Scripts\python.exe -m alembic -c backend\alembic.ini -x allow_database_access=yes -x mode=new upgrade head
```

O modo `new` recusa um banco que já tenha tabelas e faz tudo em uma única
transação: se algo falhar, nada fica pela metade. Ao final, confira:

```powershell
.venv-migracoes\Scripts\python.exe -m alembic -c backend\alembic.ini -x allow_database_access=yes -x mode=inspect current
```

A resposta deve ser `20261029_0003 (head)`.

**Fuso horário (obrigatório).** O CRM grava prospecções, reuniões e fechamentos com
o relógio do PostgreSQL. O banco local usa `America/Sao_Paulo`; o Neon usa UTC por
padrão, o que jogaria eventos das 21h às 23h59 para o dia (ou mês) seguinte nas metas.
No **SQL Editor** do Neon, com o banco `artx_crm` selecionado, rode uma vez:

```sql
ALTER DATABASE artx_crm SET timezone TO 'America/Sao_Paulo';
```

Abra uma nova consulta e confirme com `SHOW timezone;`.

## 4. Criar o administrador

Na mesma janela do PowerShell (as variáveis do passo 3 continuam valendo):

```powershell
$env:DATABASE_URL = $env:MIGRATION_DATABASE_URL
.venv-migracoes\Scripts\python.exe backend\bootstrap_admin.py
```

O script pergunta nome, e-mail e senha (a senha não aparece na tela) e recusa
criar um segundo administrador.

## 5. Limpar a janela

Feche o PowerShell, ou rode:

```powershell
Remove-Item Env:MIGRATION_DATABASE_URL, Env:DATABASE_URL, Env:MIGRATION_PRODUCTION_TARGET
```

## 6. Configurar a API no Render

No painel do serviço (Root Directory `backend`), em **Environment**:

| Variável | Valor |
| --- | --- |
| `DATABASE_URL` | URL **pooled** do Neon |
| `APP_ORIGINS` | endereço HTTPS do frontend, ex.: `https://crm.artx.com.br` |
| `APP_PUBLIC_URL` | o mesmo endereço do frontend |
| `AUTH_COOKIE_SECURE` | `true` |
| `API_DOCS_ENABLED` | `false` |
| `PYTHON_VERSION` | `3.13.18` |
| `SMTP_*` | dados do provedor de e-mail (recuperação de senha) |

`MIGRATION_DATABASE_URL` e `MIGRATION_PRODUCTION_TARGET` **não** vão para o Render:
servem só para rodar migrações a partir do seu computador.

No frontend (Vercel), configure `CRM_API_URL` com a URL HTTPS da API no Render.

## Migrações futuras

Quando houver uma revisão nova (ex.: `0004`), repita o passo 3 trocando
`-x mode=new` por `-x mode=existing -x schema_reviewed=yes` e faça um backup
(branch do Neon) antes.
