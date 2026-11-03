> Pol?tica atual: somente o administrador cria usu?rios em Configura??es ? Usu?rios (POST /usuarios). O cadastro p?blico e todas as rotas Google foram removidos da aplica??o. /cadastro redireciona para /login. Contas e hist?ricos existentes foram preservados; o login ? feito com e-mail e senha. Credenciais Google eventualmente presentes no ambiente n?o habilitam rotas removidas. As instru??es anteriores de Google/cadastro p?blico s?o hist?ricas e n?o se aplicam ? configura??o atual.

# Configurações e autenticação — ART X

## Situação verificada e implantação

A tabela `usuarios` já existia, com `nome`, `email`, `senha_hash`, `tipo` (`ADMIN`/`USUARIO`) e `ativo`, mas estava vazia. Não havia autenticação nem rotas de usuários. A implementação reutiliza essa tabela. Nenhuma conta real foi criada nos testes, e nenhum histórico comercial foi alterado.

A migração `migrations/20261020_usuarios_sessoes.sql` já foi aplicada ao banco local desta sessão. Em outro ambiente, aplicá-la dentro de uma transação, antes de iniciar a versão nova do backend. Ela cria índices de unicidade, impede administrador inativo e adiciona sessões e tentativas de login. Não recria `usuarios`, não redefine senhas e não remove registros. Caso existam múltiplos administradores, administrador inativo ou e-mails duplicados ignorando maiúsculas, a migração aborta; concilie esses casos antes de reaplicar.

O CRM passa a exigir login para todas as rotas operacionais. As funções comerciais continuam iguais. Os testes que chamam as funções diretamente continuam válidos; chamadas HTTP precisam da sessão.

## Dependências

Na raiz do projeto:

```powershell
.venv/Scripts/python.exe -m pip install -r backend/requirements-auth.txt
# Somente para executar os testes HTTP:
.venv/Scripts/python.exe -m pip install -r backend/requirements-test.txt
```

Produção: `argon2-cffi==25.1.0`, `email-validator==2.3.0`. Testes: `httpx==0.28.1`. Instaladas no ambiente virtual local. Nenhuma dependência npm foi acrescentada.

## Primeiro administrador — intervenção necessária

No terminal, a partir da raiz:

```powershell
Set-Location backend
../.venv/Scripts/python.exe bootstrap_admin.py
```

Informe nome, e-mail e uma senha exclusiva de 8 a 128 caracteres, duas vezes. A senha não aparece no terminal e não é recebida por argumento de linha de comando. O comando usa o banco configurado no `.env`, bloqueia a tabela durante a inicialização e recusa sobrescrever uma conta ou criar um segundo administrador.

Depois, abra `http://localhost:3000/login`. Acesse Configurações para adicionar usuários comuns. Não existe senha padrão, nem endpoint público para cadastrar o administrador. Não foi criado um administrador automaticamente nesta entrega.

## Segurança e sessões

- Senhas novas usam Argon2id, com salt individual. Respostas públicas usam schemas que não incluem hash ou senha; erros de validação também removem os inputs.
- A sessão usa token aleatório em cookie `HttpOnly`, `SameSite=Lax`, duração de oito horas. Só o SHA-256 do token é persistido no banco.
- Logout revoga a sessão no servidor. Desativar uma conta, mudar seu perfil ou redefinir sua senha revoga todas as sessões. Alterar a própria senha exige a senha atual e confirmação e encerra todos os dispositivos.
- A identidade é verificada no banco a cada requisição. Campos de perfil enviados pelo cliente não autorizam operações.
- Operações de escrita exigem um `Origin` permitido. O login também verifica a origem e limita dez falhas por e-mail em quinze minutos, persistidas entre processos. Não confiar em dados `isAdmin` do navegador.
- O único administrador não pode ser desativado/destituído. Não há rota para excluir usuários. O índice parcial único no PostgreSQL impede dois administradores, inclusive sob concorrência.
- O frontend utiliza `/api/crm/...`: um proxy de origem fixa no Next.js encaminha cookies e mantém a sessão no domínio do CRM. Os endereços das chamadas existentes foram ajustados; payloads e regras comerciais não foram modificados.
- O frontend bloqueia o conteúdo até verificar a sessão e oferece saída na Sidebar. Usuários comuns acessam Configurações apenas para ver permissões e atualizar a própria conta, sem listar/gerenciar outras contas.

### Variáveis

No ambiente do FastAPI (ou `.env` da aplicação):

```dotenv
APP_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
AUTH_COOKIE_SECURE=false
```

Em produção, use HTTPS, `AUTH_COOKIE_SECURE=true` e configure `APP_ORIGINS` com a origem exata do frontend. Não mantenha origens locais em produção. No servidor Next.js, `CRM_API_URL` pode indicar a URL fixa da API (padrão: `http://127.0.0.1:8000`). Essa variável não é pública. Não use `NEXT_PUBLIC_` para segredos.

### Usuários preexistentes em outros ambientes

A tabela local estava vazia. Nenhuma senha existente é alterada pela migração. Hashes Argon2 reconhecidos são verificados e podem ser rehashados após um login válido. Hashes desconhecidos ou texto puro são recusados: antes de implantar em outro banco com usuários, identifique o algoritmo legado e adote verificação compatível com rehash após login, ou um procedimento individual e autorizado de recuperação. Nunca substituir todas as senhas nem tratar conteúdo desconhecido como senha em texto puro.

## Rotas

| Método | Rota FastAPI | Acesso |
|---|---|---|
| POST | `/auth/login` | Público, com limite e validação de origem |
| POST | `/auth/logout` | Revoga o cookie atual |
| GET | `/auth/me` | Conta autenticada |
| PATCH | `/auth/me` | Atualiza nome/e-mail próprios |
| POST | `/auth/senha` | Senha atual, nova senha e confirmação |
| GET | `/usuarios` | Administrador |
| POST | `/usuarios` | Administrador; nome, e-mail, senha inicial, tipo |
| PUT | `/usuarios/{id}` | Administrador; nome, e-mail, tipo e ativo |
| POST | `/usuarios/{id}/senha` | Administrador; nova senha de outra conta |

No navegador, usar o prefixo `/api/crm`. Todas as rotas operacionais existentes exigem uma sessão válida. A raiz de saúde da API permanece pública. A documentação OpenAPI descreve os contratos, mas não concede autorização.

## Arquivos

- Backend: novos `auth.py`, `auth_models.py`, `auth_schemas.py`, `bootstrap_admin.py`, `test_auth.py`, arquivos de dependências, migração e este documento; `main.py` passou a registrar autenticação, proteção global e erros de validação sem inputs sensíveis.
- Frontend: novas páginas `app/configuracoes/page.tsx`, `app/login/page.tsx`, `app/configuracoes/configuracoes.css`, `app/api/crm/[...path]/route.ts` e `components/AuthShell.tsx`.
- `components/Sidebar.tsx`: dados da sessão e logout; Configurações já existia no menu.
- `app/layout.tsx`: provedor/guarda de autenticação e fronteira Suspense.
- Leads, Clientes, Projetos, Metas e Dashboard: somente a base dos endereços HTTP mudou para `/api/crm`, sem mudança de layout, contagem ou payloads.
- Backups anteriores às mudanças em `backups/configuracoes-20261020`.

## Testes e limites

```powershell
# Em backend:
../.venv/Scripts/python.exe -m unittest test_auth test_prospeccoes test_reunioes -v
# Em frontend:
node --test tests/metas-refresh.test.cjs
npm.cmd run build
```

Testes de autenticação usam requisições HTTP contra a aplicação real e um schema PostgreSQL isolado. Cobrem acesso anônimo, chamadas administrativas por usuário comum, criação, edição, ativação/desativação, senha própria, redefinição administrativa, revogação de sessões, proteção do administrador, concorrência, e-mail duplicado, validação de origem, limite de login e ausência de senhas nas respostas. Os testes comerciais cobrem prospecção única, reuniões por entrada, rollback e preservação dos históricos. Nenhum usuário real é alterado.

Após criar o primeiro administrador, validar manualmente no navegador o preenchimento dos modais, login/logout e navegação entre as páginas com uma conta comum. A compilação e os testes automatizados não substituem essa conferência visual.

### Resultados desta entrega

- `npm.cmd run build`: passou, incluindo TypeScript e pré-renderização das rotas.
- ESLint dos novos componentes, login, Configurações, Sidebar e proxy: passou.
- Testes HTTP/autenticação e regressões comerciais: 19 passaram em schema isolado.
- Testes frontend de atualização de Metas: quatro passaram.
- `/login`, `/configuracoes` e `/`: HTTP 200; as APIs protegidas retornam 401 sem sessão, como esperado.
- Lint global: permanecem dois erros e um aviso preexistentes em `app/projetos/page.tsx` (ordem da função de progresso e hooks de carregamento). Não são erros de compilação e não foram alterados nesta tarefa.
- Contas reais permanecem em zero. Os registros comerciais foram preservados. A migração foi aplicada localmente; falta a inicialização interativa do administrador.

Referências: [argon2-cffi](https://argon2-cffi.readthedocs.io/en/stable/api.html), [OWASP — sessões](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
