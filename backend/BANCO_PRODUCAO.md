# PostgreSQL para producao ? preparacao da Etapa 3

## Baseline reconciliada (29/10/2026)

A inspeÃ§Ã£o somente de leitura de 29/10/2026 foi incorporada Ã  baseline `20261027_0001`.
Ela reproduz as funÃ§Ãµes e os cinco triggers recuperados, a unicidade mensal de metas,
aÃ§Ãµes de FK e checks documentados no inventÃ¡rio. A baseline Ã© destinada inicialmente
exclusivamente a um banco PostgreSQL novo, vazio e isolado; nÃ£o deve ser aplicada ao
banco local existente sem um plano de migraÃ§Ã£o aprovado e backup verificado.

O arquivo `history_triggers.sql` contÃ©m as definiÃ§Ãµes recuperadas sem alteraÃ§Ãµes de
regra de negÃ³cio. As quatro migraÃ§Ãµes SQL histÃ³ricas permanecem byte a byte preservadas.
Para atualizar um banco existente, faÃ§a primeiro uma comparaÃ§Ã£o de esquema e uma
revisÃ£o formal; nÃ£o use autogenerate ou `stamp` automaticamente. RestauraÃ§Ã£o de backup
e migraÃ§Ã£o para Neon devem preservar IDs, FKs e sequÃªncias e exigem autorizaÃ§Ã£o separada.
**Nenhuma operacao de banco foi executada nesta etapa.** Este documento contem
procedimentos FUTUROS, nao autorizacao para executa-los.

## Estado da preparacao

A candidata `20261027_0001` congela o que foi comprovado nos modelos e nos quatro
SQLs historicos. Sao 13 tabelas, 92 colunas e 8 FKs no metadata, sem contar
PKs/indices de suporte. O inventario completo, coluna a coluna, com tipos,
nulabilidade, defaults, PKs, FKs, unicidades e indices esta em
[migrations/inventario_esquema.json](migrations/inventario_esquema.json).
O DDL candidato esta em [alembic/sql/initial_schema.sql](alembic/sql/initial_schema.sql).

**A baseline nao esta liberada para aplicacao.** A funcao
`public.registrar_historico_lead()` e o trigger `trigger_historico_lead`
existem como dependencias no codigo/testes, mas seus corpos originais nao estao
no repositorio. Outros triggers de atualizacao de datas tambem podem existir.
Nao foi inventado um corpo substituto. O manifesto permanece
`pending_database_inspection`; falta `history_triggers.sql`. As travas falham
antes de criar engine, tabelas comerciais ou tabela de versao.

O proximo passo depende de autorizacao para a inspecao somente de leitura ou de
DDL original confiavel fornecido pelo responsavel. Depois de revisar todas as
divergencias, versionar o DDL real, ajustar a candidata e seus hashes e so entao
alterar o status do manifesto para `confirmed`. Nao basta trocar esse status.

## Estrutura identificada e seus limites

| Dominio | Tabelas / armazenamento |
| --- | --- |
| Funil e prospeccoes | leads (prospectado_em, arquivado_em) e historico_leads |
| Reunioes | reunioes, com data_reuniao e criado_em distintos |
| Clientes/contratos | clientes: lead_id opcional unico, valor_mensal, inicio, encerramento e status |
| Entregas | projetos e checklist_items |
| Objetivos | metas: ano, mes e tres valores de meta |
| Identidade/acesso | usuarios, sessoes_usuario e tentativas_login |
| Recuperacao/verificacao | tokens_email |
| Legado Google | identidades_google e fluxos_google; preservados, sem reativar endpoints |

Nao existem tabelas separadas de prospeccoes, contratos, lancamentos de receita
ou historico de precos. Nao foram criadas tabelas ficticias para esses dominios.
Faturamento e calculado pelos endpoints a partir de clientes.

As PKs bigint usam IDENTITY ALWAYS em leads, historico, clientes, projetos,
usuarios e tentativas_login. Checklist, metas e reunioes usam autoincremento
BIGSERIAL na compilacao PostgreSQL. As demais PKs sao hashes/sub strings.
Ha FKs clientes->leads, projetos->clientes, checklist->projetos, reunioes->leads
e quatro FKs de autenticacao para usuarios com ON DELETE CASCADE.
PKs/unicidades geram indices de suporte; os indices explicitos constam do JSON
e do SQL candidato. Os checks de tipo/status de usuario e administrador ativo,
o indice parcial de no maximo um ADMIN e o indice unico lower(email) foram
preservados. Nenhuma conta e criada pelo DDL.

## Divergencias confirmadas nos arquivos; banco real ainda nao consultado

1. **DDL inicial ausente:** SQLs historicos assumem tabelas previamente criadas;
   nao formam, sozinhos, uma cadeia inicializavel.
2. **Historico:** models.HistoricoLead.lead_id nao declara FK. A documentacao
   antiga relata FK com CASCADE, mas o nome/estado atual nao foi verificado.
   A candidata nao inventa essa FK. Precisamos reconciliar antes de liberar.
3. **Trigger de movimentacao:** o endpoint PATCH /leads/{id}/fase depende do
   trigger para o historico. O backend registra a primeira prospeccao e cada
   nova entrada em REUNIAO_MARCADA na mesma transacao. Nao adicionar outro
   trigger de reunioes/prospeccoes: duplicaria responsabilidades.
4. **Metas:** falta UNIQUE(ano, mes) no modelo e nos SQLs. A API faz verificacao
   previa, vulneravel a corrida, e o PUT pode mudar o periodo. Verificar se ha
   constraint real e duplicidades antes de preparar uma correcao separada.
5. **Autenticacao:** indice usuarios_email_normalizado, indice de expiracao de
   sessao e CHECK finalidade de tokens existem no SQL historico, mas nao nos
   modelos. Foram incluidos explicitamente na candidata. Nao alterar os modelos
   nem remover esses objetos via autogenerate nesta etapa.
6. **Defaults:** criado_em de projetos/checklists/metas, flags e ordem de
   checklist e valores de metas possuem defaults Python, nao server_default.
   reunioes.criado_em e anulavel no modelo; os endpoints atuais preenchem o campo.
   Nao foram inventados defaults de servidor ou backfills.
7. **Exclusao de projeto:** FK de checklist nao declara CASCADE no modelo; a
   exclusao do projeto com tarefas pode falhar. Conferir regra real antes de alterar.
8. **Datas:** dados comerciais usam timestamp sem fuso, enquanto sessoes/tokens
   usam timestamptz. O fuso do PostgreSQL local precisa ser conhecido e preservado
   na transicao para Neon. Nao converter timestamps automaticamente nem impor UTC.
9. **Regras de indicadores:** Metas usa estoque atual do funil para prospeccoes e
   reunioes, por escolha anterior; endpoints historicos usam eventos mensais.
   Faturamento mensal tambem tem criterios distintos de corte entre endpoints.
   Esta preparacao nao corrige nem troca essas regras comerciais.
10. A migracao de primeira prospeccao faz UPDATE historico e pressupoe a coluna
    prospectado_em existente. Seu conteudo foi preservado, nao reexecutado.
    A migracao de usuarios tambem pressupoe usuarios; o SQL Google altera sua
    nulabilidade e acrescenta objetos legados. Nao reaplicar arquivos por ordem
    alfabetica sobre um banco com dados.
11. O indice parcial garante **no maximo** um administrador, nao a existencia
    de exatamente um. Bootstrap e interativo, separado e exige autorizacao.

Os relatos em documentos antigos sobre o que ja foi aplicado nao substituem
uma inspecao atual do catalogo. A candidata nao e uma copia certificada do banco.

## Inspecao do PostgreSQL real ? exige autorizacao previa

[migrations/inspecao_somente_leitura.sql](migrations/inspecao_somente_leitura.sql)
contem os comandos propostos: BEGIN READ ONLY, SELECTs em information_schema e
pg_catalog e ROLLBACK. Nao consulta linhas de clientes/leads/usuarios, hashes ou
tokens. A consulta le definicoes de funcoes e defaults, que devem ser revisadas
para garantir que nao contenham segredos antes de versionar o resultado.

Conferir versao do servidor, fuso, colunas/defaults/identity, PKs/FKs/checks,
indices, funcoes, triggers, extensoes e sequencias. A existencia da tabela
alembic_version e consultada sem presumir que ela exista. Se existir, pedir
autorizacao para ler seu version_num e compara-lo com `alembic heads`.
Esta consulta nao executa funcoes comerciais nem faz SELECT de linhas de negocio.

## Conexao: desenvolvimento e Neon

- `database.py` le o .env da raiz sem sobrescrever variaveis do processo.
- `DATABASE_URL` nao vazia tem precedencia; postgres:// e postgresql:// sao
  normalizados para postgresql+psycopg://. O driver e psycopg 3.
- Sem URL, DB_HOST/PORT/NAME/USER/PASSWORD continuam funcionando. URL.create
  protege caracteres especiais dos campos separados; senha e mantida literalmente.
  Uma URL inteira deve ter usuario/senha com percent-encoding correto; nao fazer
  encode da URL completa nem re-encode de uma URL ja fornecida pelo Neon.
- Neon (*.neon.tech) recebe por padrao verify-full, sslrootcert=system e
  channel_binding=require; modos que permitem texto puro sao recusados.
  sslmode=require explicito continua aceito, mas verify-full e recomendado.
  sslrootcert=system requer libpq >=17; psycopg[binary] fornece a libpq utilizada.
  Pode-se indicar um bundle CA confiavel com DB_SSLROOTCERT.
- Local sem opcoes TLS mantem o comportamento do driver. Nenhum fuso e alterado.
- pool_pre_ping fica habilitado; DB_POOL_SIZE/MAX_OVERFLOW/RECYCLE e
  DB_CONNECT_TIMEOUT sao configuraveis. Considerar a quantidade total de
  processos/workers antes de aumentar o pool. pre_ping nao refaz uma transacao
  comercial que falhou nem garante disponibilidade durante suspensao do Neon.
- DB_POOL_MODE=null desativa o pool local quando apropriado. Em endpoint Neon
  -pooler, prepared statements automaticos sao desativados conservadoramente.
  DB_PREPARE_THRESHOLD permite ajuste explicito. Locks do login sao transacionais,
  nao locks de sessao; o pooler ainda precisa de teste funcional isolado.
- MIGRATION_DATABASE_URL e exclusiva do Alembic, obrigatoria e direta (sem
  -pooler). Nao ha fallback para a URL/DB_* da API. Nao foi preenchida nem usada.

Os dois .env.example nao contem credenciais. O da raiz documenta as novas
opcoes. Nenhuma URL externa foi colocada no .env local ou no frontend.

## Alembic: preparacao e identificacao de versao

Instalacao de ferramentas, sem tocar em banco:
```sh
python -m pip install -r backend/requirements-migrations.txt
python -m alembic -c backend/alembic.ini heads
python -m alembic -c backend/alembic.ini history
```

heads/history mostram os arquivos versionados, NAO a versao instalada no banco.
Nao executar current ou check sem autorizacao para acesso ao banco.
Nao colocar sqlalchemy.url com segredo no INI.
Os arquivos SQL antigos permanecem em migrations/ com hashes no manifesto.
A baseline candidata incorpora apenas seus efeitos de estrutura conhecidos em
um banco novo; nao executa backfill nem cria contas/registros de exemplo.
Future revisions devem ter SQL explicito e revisado. Autogenerate e apenas
rascunho: nao cobre integralmente triggers, funcoes, checks, sequencias ou regras
de negocio. Objetos legados nao modelados sao preservados e drops de tabelas/
colunas gerados automaticamente sao bloqueados para revisao.

## Caminho A ? banco NOVO, vazio, apos completar e autorizar

1. Concluir a inspecao/reconciliacao e os artefatos da baseline. Rever hashes.
2. Obter autorizacao para provisionar um banco isolado e depois aplica-la.
3. Configurar MIGRATION_DATABASE_URL para esse destino direto, nunca para o
   PostgreSQL local. Nenhum comando abaixo cria o banco.
4. Somente com aprovacao, o comando futuro e:
```sh
python -m alembic -c backend/alembic.ini -x allow_database_access=yes -x mode=new upgrade head
```
5. O modo new recusa public com tabelas, views, sequencias ou funcoes existentes.
   A transacao unica deve desfazer DDL e versao se qualquer passo falhar.
6. Validar insercoes via API, IDs, triggers, rollback e regras em ambiente isolado.
   O primeiro administrador e criado separadamente pelo bootstrap interativo,
   mediante autorizacao; nenhum dado inicial ou senha e embutido na baseline.

Esse comando permanece bloqueado hoje, mesmo se os flags forem fornecidos.

## Caminho B ? banco EXISTENTE, sem recriar estrutura

1. Backup completo e teste de restauracao aprovados.
2. Comparar a estrutura real com a baseline completada: nao considerar tabelas
   existentes como prova de equivalencia. Resolver nomes/FKs/defaults/triggers,
   dados incompativeis e versoes de PostgreSQL antes de adotar uma revisao.
3. Somente se houver equivalencia comprovada, apos autorizacao especifica,
   planejar stamp na revisao correspondente. Stamp grava alembic_version,
   nao aplica/corrige DDL. Nunca usar stamp como forma de ignorar divergencias.
4. Se houver divergencias, preparar migracao de reconciliacao aditiva separada,
   com pre-condicoes para o estado real. Nao existe migracao de reconciliacao
   aplicada ou presumida nesta etapa.
5. Futuras atualizacoes exigem MIGRATION_DATABASE_URL, mode=existing,
   allow_database_access=yes e schema_reviewed=yes. Upgrade recusa banco
   existente sem tabela de versao; nao faz stamp automatico.
6. Downgrade fica bloqueado. Reversao de uma mudanca exige plano proprio,
   backup restauravel e autorizacao; nao remover colunas/tabelas para voltar.

Nenhum stamp, current, upgrade, downgrade, check/autogenerate contra banco ou
SQL de migracao foi executado nesta preparacao.

## Backup e restauracao ? somente depois de autorizados

Usar pg_dump/pg_restore estaveis, compat?veis com a versao real do servidor;
nao escolher uma versao experimental do PostgreSQL. O pg_dump nao pode ser de
uma major inferior a do servidor de origem. Preferir mesma major no destino,
ou major superior suportada apos teste. Conferir extensoes disponiveis no Neon.

Usar servicos libpq configurados FORA do Git e arquivo de senhas com permissoes
restritas, sem senhas na linha de comando, no INI ou no historico do terminal.
Exemplo de nomes de servico: crm_origem e crm_neon_destino (nao configurados aqui).
O diretorio backups/ e ignorado pelo Git; contem dados pessoais e hashes,
portanto precisa de armazenamento privado, controle de acesso e criptografia.

Comandos futuros de referencia, NAO executados:
```sh
pg_dump --dbname="service=crm_origem" --format=custom --no-owner --no-acl --file=backups/crm-pre-migracao.dump
pg_restore --list backups/crm-pre-migracao.dump
pg_restore --dbname="service=crm_neon_destino" --no-owner --no-acl --single-transaction --exit-on-error backups/crm-pre-migracao.dump
```

Restaurar exclusivamente em destino vazio previamente autorizado, nunca sobre
o banco local. Nao usar --clean, --create, drop_all nem desabilitar FKs/triggers
automaticamente. O dump completo guarda definicoes, dados, IDs, sequencias e
seus estados, relacionamentos, funcoes e triggers que existirem na origem.
pg_restore --list apenas lista um arquivo local; a restauracao executa o SQL
contido no dump, logo o arquivo deve ser confiavel e revisado.
Nao copiar tabelas manualmente com novos IDs nem importar apenas CSV.
Nao restaurar data-only sobre uma baseline com triggers ativos sem plano:
isso pode duplicar historicos. O caminho de restauracao completa em vazio e
distinto do caminho de inicializacao do Alembic; nao executar os dois no mesmo alvo.

## Corte para Neon, preservando dados e sequencias

1. Validar restauracao em um destino de ensaio vazio e comparar contagens e
   integridade sem expor dados pessoais. Checar todas as tabelas, inclusive
   leads arquivados, reunioes, tokens, usuarios e legado Google.
2. Validar cada PK/FK, unicidade e os indices; nao ignorar erros de restauracao.
3. Conferir a sequencia associada a cada coluna identity/serial e seu estado
   em relacao ao maior ID importado. Nao chamar nextval apenas para testar,
   porque avanca a sequencia. O dump completo ja inclui SEQUENCE SET.
   Se houver discrepancia, preparar e autorizar setval separadamente, incluindo
   tratamento de tabelas vazias. Nao resetar sequencias a 1.
4. Conferir TimeZone e timestamps com o comportamento local antes do corte.
   Nao mudar o tipo de coluna ou reinterpretar datas automaticamente.
5. Preservar hashes de senha e papeis. Qualquer invalidacao de sessoes/tokens
   e uma decisao de seguranca separada; nao apaga-los automaticamente.
6. Em janela autorizada, suspender escritas do CRM para o snapshot final,
   gerar novo dump, restaurar no destino final vazio e validar novamente.
   pg_dump e consistente, mas nao replica escritas posteriores ao snapshot.
7. So apos homologacao trocar as variaveis na hospedagem. Manter origem e
   backup intactos para retorno controlado. Evitar escritas simultaneas nas
   duas bases, que impediriam rollback simples.
8. Adotar Alembic no banco restaurado somente apos equivalencia comprovada,
   seguindo o caminho B. Nunca executar a baseline inicial sobre ele.

## Autorizacoes ainda necessarias e riscos

Exigem autorizacao: inspecao real (mesmo READ ONLY), dump de dados, provisionar
destino, restaurar, aplicar qualquer migracao/stamp, conciliar duplicidades,
setval, alterar fuso/permissoes, bootstrap do administrador e corte de conexao.
As travas reduzem acidentes, mas nao substituem controle de acesso no banco.
Um operador ainda poderia executar SQL manualmente fora do Alembic.

Riscos principais: cascatas desconhecidas, ausencia do trigger original,
reaplicar backfills, restaurar sobre dados existentes, sequencias incorretas,
diferencas de fuso, duplicidade de metas e divergencias entre modelo e catalogo.
Nenhum desses riscos foi resolvido alterando dados ou regras nesta etapa.

## Validacao segura disponivel

```sh
python -m unittest discover -s backend/tests -v
python -m pip check
```

Usar o ambiente de validacao com requirements-test.txt e requirements-migrations.txt.
Essa pasta contem apenas testes sem banco, com Engine.connect e psycopg.connect
bloqueados, compilacao de DDL, inventario, hashes e configuracao. Nao executar
unittest discover generico em backend: os testes antigos dependem de PostgreSQL
e criam schemas/aplicam SQL. Falta testar DDL e transacoes num PostgreSQL isolado;
a candidata completa continua bloqueada ate recuperar os objetos faltantes.

## Fontes oficiais

- [Alembic: autogenerate exige revisao](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
- [SQLAlchemy: URL.create e caracteres especiais](https://docs.sqlalchemy.org/en/20/core/engines.html)
- [Neon: TLS](https://neon.com/docs/connect/connect-securely)
- [Neon: conexao direta para migracoes/dumps](https://neon.com/docs/connect/connection-pooling)
- [PostgreSQL: pg_dump](https://www.postgresql.org/docs/current/app-pgdump.html)
- [PostgreSQL: pg_restore](https://www.postgresql.org/docs/current/app-pgrestore.html)

## Registro das verificacoes desta preparacao

- 19 testes unitarios/estaticos em backend/tests passaram, sem banco.
- Mais 4 testes basicos da API passaram com conexoes bloqueadas: OpenAPI,
  acesso anonimo, schemas e Argon2.
- Sintaxe de todos os Python conferida; DDL dos 13 modelos compilado offline.
- pip check passou com Alembic 1.20.1, Mako 1.3.12 e MarkupSafe 3.0.3.
- alembic heads e history leram apenas arquivos e reconheceram 20261027_0001.
  Isso NAO significa que a revisao esteja instalada ou pronta para aplicacao.
- Os 4 SQLs historicos permaneceram identicos; .env original preservado.
- Inspecao real nao executada. Nenhum upgrade, stamp, downgrade, create_all,
  drop_all, backup, restauracao ou transacao em PostgreSQL foi executado.
- Sem testes de TLS real, PgBouncer, integridade ou triggers em servidor nesta fase.
- Aviso preexistente: Starlette TestClient recomenda futura migracao HTTPX->HTTPX2;
  os testes basicos passaram com as dependencias atuais.

As regras de fase/status e os limites de mes/valores validados pelo Pydantic
nao equivalem automaticamente a CHECKs no banco. Os checks comerciais que nao
aparecem nos modelos/SQLs precisam ser conferidos no catalogo antes da liberacao.

Arquivos desta etapa:
- .env.example e AMBIENTE.md (documentacao de configuracao).
- backend/database.py e backend/db_config.py.
- backend/requirements-migrations.txt e backend/requirements-test.txt.
- backend/alembic.ini e backend/schema_guard.py.
- backend/alembic/env.py, script.py.mako e versions/20261027_0001_initial.py.
- backend/alembic/sql/initial_schema.sql e manifest.json.
- backend/migrations/inventario_esquema.json e inspecao_somente_leitura.sql.
- backend/tests/test_database_config.py e test_schema_preparation.py.
- backend/BANCO_PRODUCAO.md.

Pronto para testes estaticos e revisao. O ensaio COMPLETO em um PostgreSQL
isolado depende de recuperar os triggers/funcoes e reconciliar as divergencias
antes de desbloquear a baseline. Um ensaio parcial do DDL tabular tambem exige
autorizacao especifica; nao contornar as travas para usar o CRM incompleto.

## Ensaio isolado da baseline (não executado)

1. Criar um banco descartável com nome explicitamente distinto do banco local/produção e credenciais próprias.
2. Confirmar `current_database()` e que não existem tabelas, schemas de aplicação ou objetos CRM.
3. Definir `MIGRATION_DATABASE_URL` somente para esse banco e manter `DATABASE_URL` fora do processo.
4. Executar `alembic upgrade 20261027_0001` de forma controlada, capturando logs.
5. Inspecionar catálogo: 13 tabelas, 92 colunas, 9 FKs, 23 índices, 5 triggers e 9 sequências.
6. Validar checks, unicidades, ações de FK, defaults e identity; executar testes funcionais dos triggers em transação descartável.
7. Aprovar somente se não houver objetos duplicados, divergências de nomes/ações ou erros de trigger; em qualquer falha descartar apenas o banco de ensaio e corrigir a baseline.
