# Ambiente do CRM ART X

Referencia da Etapa 2: 27/10/2026. Nenhuma migracao e executada pela instalacao.

## Versoes

| Ferramenta | Encontrada no computador | Referencia para desenvolvimento e producao |
| --- | --- | --- |
| Node.js | 22.12.0 | 22.23.4 LTS (mesma linha 22) |
| npm | 10.9.0 | 10.9.9, distribuido com o Node recomendado |
| Python | 3.13.1 | 3.13.18, CPython convencional, mesma linha 3.13 |
| Next.js | 16.4.0 | 16.4.1, correcao estavel de seguranca |
| eslint-config-next | 16.4.0 | 16.4.1 |

`frontend/.nvmrc`, `frontend/package.json` e `.python-version` registram as referencias.
Nao instalam nem substituem runtimes globais. Na Vercel, selecionar Node.js 22.x
e confirmar nos logs que o patch e pelo menos 22.23.4. No Render, configurar
`PYTHON_VERSION=3.13.18`, especialmente se o Root Directory for `backend`.
Novos patches de seguranca devem ser revisados periodicamente.

React/React DOM 19.3.0, TypeScript, Tailwind e dnd-kit foram preservados.
O `package-lock.json` fixa a arvore do frontend; usar `npm ci`, nao `npm update`.
O Next.js corrigido inclui as correcoes de React Server Components usadas pelo framework.

## Backend

Na raiz do repositorio, criar um ambiente NOVO com o Python recomendado. Nao
sobrescrever um ambiente em uso. Exemplo Windows, caso `.venv` ainda nao exista:

```powershell
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Linux/Render, com Root Directory `backend` e ambiente virtual da plataforma:

```sh
python -m pip install -r requirements.txt
python -m pip check
python -m uvicorn main:app --host 0.0.0.0 --port "$PORT"
```

`requirements.txt` inclui runtime e transitivas com versoes exatas;
`requirements-auth.txt` continua sendo incluido para Argon2 e validacao de e-mail.
Ele sozinho nao instala toda a API. `requirements-test.txt` inclui o runtime
completo e HTTPX com suas dependencias. Nao foram adicionados extras de Google,
multipart, WebSockets ou servidores alternativos que a aplicacao nao utiliza.
O driver e `psycopg` 3 com o extra `binary`, inclusive sua versao fixada, para
dispensar compilacao/libpq do sistema nos ambientes suportados.

Antes de iniciar a API, configurar as variaveis reais e um banco com o esquema
ja preparado. A instalacao das bibliotecas nao cria tabelas, triggers nem usuarios.
O preparo do esquema e assunto de uma etapa posterior.

## Frontend

No diretorio `frontend`, com a versao de Node indicada em `.nvmrc`:

```sh
npm ci
npm run lint
npm run typecheck
npm test
npm run build
npm start
```

Em PowerShell com scripts bloqueados, usar `npm.cmd` em vez de `npm`;
nao e necessario mudar a politica de execucao do Windows.
No primeiro checkout, caso o TypeScript reclame de tipos gerados de rotas,
executar `npx next typegen` antes de `npm run typecheck`; o build tambem os gera.
O build usa Geist via `next/font/google` e precisa de acesso a Google Fonts.
Os testes Node existentes usam dados simulados e nao escrevem no PostgreSQL.

## Variaveis de ambiente

Os modelos `.env.example` da raiz e de `frontend` cobrem as variaveis utilizadas.
Nao sobrescrever um `.env` existente nem copiar segredos para os modelos.

- Backend: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.
- Autenticacao: `APP_ORIGINS`, `APP_PUBLIC_URL`, `AUTH_COOKIE_SECURE`.
- Recuperacao/verificacao de e-mail: `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`,
  `SMTP_FROM`, `SMTP_USER`, `SMTP_PASSWORD`.
- Servidor Next.js: `CRM_API_URL`, sem prefixo `NEXT_PUBLIC_`.

Em desenvolvimento, copiar os modelos somente se os arquivos de destino ainda
nao existirem. Em producao, usar as variaveis dos paineis de hospedagem: HTTPS,
origens reais e `AUTH_COOKIE_SECURE=true`. A Etapa 3 acrescenta suporte a `DATABASE_URL`, com fallback para `DB_*`.
Consulte `backend/BANCO_PRODUCAO.md` para TLS e migracoes separadas. Google e cadastro publico continuam desativados.

## Limite dos testes PostgreSQL

Nao executar `unittest discover` contra as credenciais locais ou de producao.
Os quatro arquivos `backend/test_*.py` criam schemas e parte deles executa SQL
de migracoes; usam por padrao o mesmo engine carregado do ambiente da aplicacao.
Precisam de uma instancia de teste separada, com os pre-requisitos de triggers
preparados, antes de qualquer execucao. Na Etapa 2 essas suites nao sao executadas.
Importacao, sintaxe, validacao de schemas e verificacao de hashes podem ser
conferidas sem conectar ao banco. Isso nao substitui os testes de integracao.

## Referencias oficiais

- [Next.js: correcao de 14/10/2026](https://nextjs.org/blog/nextjs-security-update-october-14-2026)
- [Node.js: versoes publicadas](https://nodejs.org/dist/index.json)
- [Python 3.13.18](https://www.python.org/downloads/release/python-31318/)

## Resultado da validacao da Etapa 2

Executada no Windows com Node.js 22.23.4/npm 10.9.9 portateis e Python 3.13.1.
O Node portatil foi validado com o SHA-256 publicado pelo projeto Node.js;
nao houve substituicao dos runtimes globais. O Python 3.13.18 recomendado ainda
precisa ser instalado/selecionado nos ambientes de desenvolvimento e hospedagem.
As verificacoes locais nao substituem uma execucao em Linux/Render.

- `npm ci`: passou em instalacao limpa; npm reportou zero vulnerabilidades.
- `npm run build`: passou com Next.js 16.4.1, incluindo TypeScript e 14 paginas
  geradas. A primeira tentativa restrita falhou ao baixar Geist/Geist Mono;
  a execucao com acesso a Google Fonts passou sem alterar layout ou fontes.
- `npm test`: 8 testes passaram (atualizacao de metas e filtros de projetos).
- Backend: instalacao limpa de `requirements-test.txt` passou; `pip check`
  retornou `No broken requirements found`.
- Sintaxe de todos os arquivos Python e 4 testes basicos passaram: importacao
  e OpenAPI/modelos, resposta publica e rejeicao de acesso anonimo, schemas
  Pydantic/e-mail/compatibilidade de status, hash e verificacao Argon2id.
  Engine.connect e psycopg.connect foram bloqueados explicitamente nesses
  testes; nenhuma conexao ao PostgreSQL foi permitida.
- Consulta OSV para os 28 pacotes instalados (runtime e testes, excluindo pip):
  nenhuma vulnerabilidade conhecida retornada em 27/10/2026. Isso nao constitui
  garantia contra vulnerabilidades ainda nao catalogadas.
- `npm run lint`: falhou com 2 erros e 1 aviso em
  `frontend/app/projetos/Projetos.tsx`: uso de `carregarProgressoProjetos` antes
  da declaracao (linha 125), setState sincrono em efeito (linha 133) e dependencia
  `carregarDados` ausente (linha 134). Sao preexistentes: as configuracoes
  index/core-web-vitals/typescript do eslint-config-next 16.4.0 e 16.4.1 foram
  comparadas e sao identicas, assim como a versao do plugin de hooks e o codigo.
  Foram mantidos para uma etapa de correcao do codigo, sem desativar regras.
- Avisos adicionais: ESLint 9.39.5 esta fora de suporte (uma troca de major
  requer revisao separada); TestClient do Starlette avisa sobre a futura
  substituicao de HTTPX por HTTPX2; Next ignora um lockfile externo ao repositorio
  no perfil do Windows. Nenhum desses avisos impediu o build ou os testes.
- Os testes PostgreSQL nao foram executados, pois nao foi disponibilizado um
  banco de teste separado. Nenhuma migracao foi executada.

Os hashes do codigo de negocio e do `.env` original foram preservados. Somente
manifestos/lockfile, referencias de runtime e esta documentacao foram alterados.
Nao houve commit nem publicacao. A proxima etapa pode prosseguir mediante
autorizacao; os erros de lint e os testes isolados de integracao continuam pendentes.
