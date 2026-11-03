# Inspecao somente de leitura ? CRM ART X ? 29/10/2026

## 1. Execucao e evidencia de seguranca

Inspecao local concluida. O SQL foi revisado integralmente, e seu hash SHA-256
foi conferido antes da execucao: `d6c9a8ad220f31c32e0a8a905d3f4febe62051bc6ea8ca0f46e45098ee605b5e`.
Somente consultas de metadados e comandos de controle BEGIN READ ONLY,
SET LOCAL de timeout e ROLLBACK foram executados. Uma consulta adicional de
configuracao confirmou os dois flags read-only e o endereco de servidor local.

- default_transaction_read_only = on.
- transaction_read_only = on.
- Encerramento com ROLLBACK confirmado e conexao fechada.
- A conta local configurada foi mantida; nao houve alteracao de papeis ou
  permissoes. A restricao foi imposta na sessao e na transacao.
- Nenhuma tabela comercial foi consultada, nem mesmo para contar registros.
- Nenhum DDL/DML, migracao, stamp, backup, restauracao ou nextval/setval executado.
- Nenhuma credencial, hash de senha, token, conta ou dado de cliente foi exportado.
- A coleta de 27/10 foi preservada; os metadados desta coleta sao identicos.
- Codigo, SQL de inspecao, SQLs historicos, baseline candidata e .env preservados.

Servidor identificado: PostgreSQL 18.6 (server_version_num=180006).
Fuso: America/Sao_Paulo. Extensao retornada: plpgsql 1.0.
A tabela public.alembic_version NAO existe; nao foi criada nem feito stamp.

A evidencia completa esta em [estrutura.json](estrutura.json).
Os corpos originais estao em [definicoes_recuperadas.txt](definicoes_recuperadas.txt).
O comparativo esta em [divergencias.json](divergencias.json).
Esses arquivos sao documentacao local, nao uma migracao aplicada ou publicacao.

## 2. Estrutura encontrada

13 tabelas, 92 colunas, 23 indices, 9 sequencias e 5 triggers de aplicacao.
Foram recuperadas as duas funcoes relacionadas aos triggers do CRM.
As 113 constraints retornadas se dividem em 72 NOT NULL, 13 PKs, 9 FKs,
15 CHECKs e 4 UNIQUEs. Todas retornaram convalidated=true.

Tabelas: `checklist_items`, `clientes`, `fluxos_google`, `historico_leads`, `identidades_google`, `leads`, `metas`, `projetos`, `reunioes`, `sessoes_usuario`, `tentativas_login`, `tokens_email`, `usuarios`.

Nomes, tipos e conjunto das colunas coincidem com os modelos atuais.
Nao foram encontrados campos/tabelas faltantes ou extras no conjunto inspecionado.
Isso nao e uma verificacao dos registros armazenados ou de seus valores.
Todas as definicoes, defaults e nulabilidades constam em estrutura.json.

## 3. Funcao e trigger de historico

public.registrar_historico_lead() foi recuperada integralmente do catalogo.
trigger_historico_lead e BEFORE UPDATE ON public.leads, FOR EACH ROW,
habilitado em modo normal (tgenabled=O).

Pelo corpo recuperado:
1. Compara OLD.fase e NEW.fase usando IS DISTINCT FROM.
2. Somente quando a fase realmente muda, registra em historico_leads:
   OLD.id, OLD.fase, NEW.fase e CURRENT_TIMESTAMP.
3. Mesmo sem mudanca de fase, atribui CURRENT_TIMESTAMP a NEW.atualizado_em.
4. Retorna NEW, permitindo a atualizacao do lead.

Nao e disparado no cadastro (nao ha evento INSERT nesse trigger).
Nao duplica o historico ao atualizar mantendo a mesma fase.
Nao cria reunioes nem preenche prospectado_em: essas responsabilidades
continuam no endpoint de transicao. Nao adicionar um segundo mecanismo para
esses eventos sem avaliar duplicidades. A escrita do historico faz parte da
mesma transacao do UPDATE. A funcao nao foi chamada/testada com alteracoes
nesta inspecao; a descricao acima decorre da definicao e do estado do catalogo.

public.atualizar_data_modificacao() atribui CURRENT_TIMESTAMP a
NEW.atualizado_em e retorna NEW. Os cinco vinculos reais sao:
| Tabela | Trigger | Funcao | Estado |
| --- | --- | --- | --- |
| clientes | trigger_atualizar_clientes | atualizar_data_modificacao | habilitado (O) |
| leads | trigger_historico_lead | registrar_historico_lead | habilitado (O) |
| metas | trigger_atualizar_metas | atualizar_data_modificacao | habilitado (O) |
| projetos | trigger_atualizar_projetos | atualizar_data_modificacao | habilitado (O) |
| usuarios | trigger_atualizar_usuarios | atualizar_data_modificacao | habilitado (O) |


## 4. Relacionamentos, unicidades e checks

| Tabela | Constraint | Definicao |
| --- | --- | --- |
| checklist_items | fk_checklist_projeto | `FOREIGN KEY (projeto_id) REFERENCES projetos(id) ON DELETE CASCADE` |
| clientes | fk_cliente_lead | `FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL` |
| fluxos_google | fluxos_google_usuario_id_fkey | `FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE` |
| historico_leads | fk_historico_lead | `FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE` |
| identidades_google | identidades_google_usuario_id_fkey | `FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE` |
| projetos | fk_projeto_cliente | `FOREIGN KEY (cliente_id) REFERENCES clientes(id)` |
| reunioes | fk_reuniao_lead | `FOREIGN KEY (lead_id) REFERENCES leads(id)` |
| sessoes_usuario | sessoes_usuario_usuario_id_fkey | `FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE` |
| tokens_email | tokens_email_usuario_id_fkey | `FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE` |


Ha cascata do historico quando um lead e fisicamente removido, cascata de
checklists quando o projeto e removido e cascatas das quatro tabelas dependentes
de usuarios. clientes.lead_id usa SET NULL. Projetos->clientes e reunioes->leads
usam NO ACTION (padrao).

O codigo atual arquiva leads em vez de remove-los fisicamente. Isso preserva
o historico no fluxo normal; nao equivale a proibir um DELETE fisico externo.

Unicidades declaradas:
| Tabela | Constraint | Colunas |
| --- | --- | --- |
| clientes | clientes_lead_id_key | UNIQUE (lead_id) |
| identidades_google | identidades_google_usuario_id_key | UNIQUE (usuario_id) |
| metas | uq_meta_mes | UNIQUE (ano, mes) |
| usuarios | usuarios_email_key | UNIQUE (email) |


A uq_meta_mes JA EXISTE e e UNIQUE(ano, mes). A pendencia anterior era a
ausencia no modelo/baseline, nao uma ausencia no PostgreSQL local.
Nao criar uma segunda constraint equivalente.

Tambem existem usuarios_email_normalizado (unico em lower(email)) e
usuarios_um_admin (unico parcial para tipo=ADMIN). Este ultimo assegura no
maximo um ADMIN, nao a existencia de uma conta administrativa.

Checks encontrados (expressoes completas em estrutura.json):
| Tabela | Check |
| --- | --- |
| clientes | chk_datas_cliente |
| clientes | clientes_status_check |
| clientes | clientes_valor_mensal_check |
| leads | leads_fase_check |
| metas | metas_mes_check |
| metas | metas_meta_faturamento_check |
| metas | metas_meta_prospeccoes_check |
| metas | metas_meta_reunioes_check |
| projetos | projetos_prioridade_check |
| projetos | projetos_status_check |
| reunioes | reunioes_status_check |
| tokens_email | tokens_email_finalidade_check |
| usuarios | usuarios_admin_ativo |
| usuarios | usuarios_status_acesso_check |
| usuarios | usuarios_tipo_check |


Eles cobrem fases, status, prioridades, mes 1..12, valores nao negativos,
intervalo de datas do cliente, tipos/status de acesso e finalidade de tokens.

## 5. Divergencias confirmadas

- historico_leads.lead_id: FK fk_historico_lead CASCADE existe no banco, mas
  nao e declarada no modelo nem na candidata.
- clientes.lead_id: banco SET NULL; modelo/candidata omitem essa acao.
- checklist_items.projeto_id: banco CASCADE; modelo/candidata omitem a acao.
  A suspeita anterior de FK local impedir excluir projetos com checklist nao
  se confirma: a divergencia esta na representacao em codigo/candidata.
- metas: falta a uq_meta_mes na representacao atual dos modelos/candidata.
- metas.id, reunioes.id e checklist_items.id sao IDENTITY ALWAYS no banco;
  modelo/candidata usam autoincremento implicito/BIGSERIAL.
- reunioes.criado_em e NOT NULL DEFAULT CURRENT_TIMESTAMP no banco, mas o
  modelo o permite nulo e nao declara o default.
- 12 defaults de servidor nao estao declarados de forma equivalente nos modelos:
| Coluna | Default no banco | Default Python do modelo |
| --- | --- | --- |
| leads.fase | 'PROSPECTAR'::character varying | (ausente) |
| metas.meta_prospeccoes | 0 | 0 |
| metas.meta_reunioes | 0 | 0 |
| metas.meta_faturamento | 0 | 0 |
| metas.criado_em | CURRENT_TIMESTAMP | datetime.now |
| metas.atualizado_em | CURRENT_TIMESTAMP | datetime.now |
| reunioes.status | 'AGENDADA'::character varying | AGENDADA |
| reunioes.criado_em | CURRENT_TIMESTAMP | (ausente) |
| projetos.criado_em | CURRENT_TIMESTAMP | datetime.now |
| checklist_items.concluido | false | False |
| checklist_items.ordem | 0 | 0 |
| checklist_items.criado_em | CURRENT_TIMESTAMP | datetime.now |


Os literais de usuarios.tipo e usuarios.status_acesso sao semanticamente
equivalentes entre modelo e banco, apesar das diferencas de aspas/casts na
serializacao. Nao foram contados como erros.

Doze checks do catalogo nao estao nos modelos. Um deles (finalidade do token)
ja consta do SQL historico/candidata; faltam onze checks reais na candidata.
Faltam as duas funcoes e os cinco triggers na candidata.
Os indices ix_public_* gerados na candidata diferem dos nomes reais
ix_sessoes_usuario_usuario_id, ix_tentativas_login_chave e
ix_tokens_email_usuario_id. Ajustar os nomes futuramente, sem duplicar indices
equivalentes. FKs nomeadas no banco tambem devem ser reconciliadas com o DDL.

## 6. Sequencias e IDs

| Sequencia | Tipo | Inicio | Incremento | Cache | Ciclica |
| --- | --- | --- | --- | --- | --- |
| checklist_items_id_seq | bigint | 1 | 1 | 1 | False |
| clientes_id_seq | bigint | 1 | 1 | 1 | False |
| historico_leads_id_seq | bigint | 1 | 1 | 1 | False |
| leads_id_seq | bigint | 1 | 1 | 1 | False |
| metas_id_seq | bigint | 1 | 1 | 1 | False |
| projetos_id_seq | bigint | 1 | 1 | 1 | False |
| reunioes_id_seq | bigint | 1 | 1 | 1 | False |
| tentativas_login_id_seq | bigint | 1 | 1 | 1 | False |
| usuarios_id_seq | bigint | 1 | 1 | 1 | False |


Foram consultadas apenas definicoes de sequencias, sem last_value, nextval,
setval ou IDs das tabelas. Seus valores atuais e a correspondencia com o maior
ID nao foram verificados. Essa validacao devera integrar o ensaio autorizado
de restauracao. Nao reiniciar sequencias nem converter IDENTITY ALWAYS em
serial por conveniencia. Definicoes de propriedade/permissoes de sequencias
nao fazem parte das colunas retornadas por este roteiro.

## 7. Arquivos que precisam de ajustes APOS autorizacao

Nenhum desses ajustes foi implementado nesta inspecao:

- backend/models.py: FKs/acoes, unicidade mensal, identity, checks e defaults.
- backend/auth_models.py: checks/indices presentes no SQL mas ausentes no modelo,
  incluindo finalidade de tokens, e-mail normalizado e expiracao de sessoes.
- backend/alembic/sql/initial_schema.sql: reproduzir os objetos reais e seus nomes.
- backend/alembic/sql/history_triggers.sql: criar usando as duas definicoes
  recuperadas e os cinco triggers, sem inventar corpos ou executar o arquivo.
- backend/alembic/sql/manifest.json: revisar hashes/status depois de concluir
  e testar a candidata. Nao desbloquear apenas por ter coletado o catalogo.
- backend/migrations/inventario_esquema.json e backend/BANCO_PRODUCAO.md:
  atualizar as divergencias agora confirmadas.
- backend/tests/test_schema_preparation.py: ampliar verificacoes contra as
  definicoes recuperadas antes do ensaio em PostgreSQL isolado.

Os quatro SQLs historicos devem continuar preservados, sem reaplicacao
automatica. database.py, credenciais e frontend nao precisam ser alterados para
concluir esta inspecao. Nenhum arquivo de aplicacao ou baseline foi editado.

## 8. Informacoes suficientes e limites

SIM: a definicao original faltante foi recuperada, e ha informacao suficiente
para reconciliar a baseline dos objetos do CRM cobertos pelo roteiro.
Isso nao aprova a candidata atual: ela continua bloqueada e nao foi alterada.
A proxima etapa e ajustar os ARQUIVOS apos autorizacao e entao preparar um
ensaio em um PostgreSQL separado, tambem autorizado.

Nao houve teste funcional do trigger, movimentacao de cards, login gravando
sessoes, contagem de dados, validacao de valores comerciais ou restauracao.
A consulta nao inventaria papeis/permissoes, RLS, collation/encoding do banco,
propriedade de sequencias nem todas as funcoes sem vinculo aos triggers.
Esses itens nao devem ser considerados automaticamente certificados.

## 9. Riscos a tratar antes de producao

1. DELETE fisico de lead pode apagar historico em cascata quando nao houver
   outra FK impedindo a remocao. Preservar arquivamento e revisar privilegios.
2. Nao executar a candidata atual nem stamp sobre o banco existente. Ela ainda
   diverge do catalogo e o banco nao possui tabela de versao Alembic.
3. Reproduzir a uniq mensal e checks existentes sem criar duplicatas ou mudar
   regras comerciais.
4. Preservar IDs/identity e validar sequencias na restauracao autorizada.
5. Manter a semantica de America/Sao_Paulo para timestamps sem fuso no Neon.
6. A funcao usa historico_leads sem qualificacao de schema; revisar search_path
   e privilegios para producao, sem modificar a definicao capturada nesta etapa.
7. Recuperar DDL nao substitui teste funcional/rollback/concorrencia em banco
   isolado. Nenhum teste que escreve foi executado na base local.
8. Revisar os itens de seguranca/locale fora do roteiro antes da publicacao.

Nao houve commits, publicacao, backup, restauracao ou alteracao de dados.
Aguardando autorizacao para os proximos ajustes; sem operacoes adicionais no banco.
