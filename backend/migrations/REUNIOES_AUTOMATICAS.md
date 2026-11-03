> Regra de visualiza??o atualizada em 20/10/2026: por solicita??o do usu?rio, Metas e os cards de metas do Dashboard mostram o funil atual. Prospec??es contam leads n?o arquivados em FOLLOW_UP, REUNIAO_MARCADA ou REMARKETING_FUTURO; reuni?es contam leads n?o arquivados em REUNIAO_MARCADA. O m?s seleciona as metas para compara??o, n?o a compet?ncia dos cards. O faturamento mant?m sua regra mensal. Os eventos e os endpoints hist?ricos mensais continuam preservados e podem ter totais diferentes do funil atual. Nenhuma migra??o ou reinicializa??o dos dados ? necess?ria.

# Reuniões automáticas e preservação do histórico

## Migração

Aplicar `20261016_preservar_leads_historicos.sql` no banco do CRM **antes** de iniciar o backend atualizado. A migração já foi aplicada no banco local desta sessão.

Em um cliente PostgreSQL conectado ao banco correto, executar em uma transação:

```sql
BEGIN;
SET LOCAL lock_timeout = '5s';
ALTER TABLE public.leads
    ADD COLUMN IF NOT EXISTS arquivado_em timestamp without time zone;
COMMIT;
```

A operação adiciona apenas uma coluna anulável. Não remove linhas, não altera as FKs e não preenche reuniões retroativamente. Pode ser executada novamente. Não remover a coluna depois de arquivar leads: ela identifica os registros retirados do Kanban.

## Comportamento

- `PATCH /leads/{id}/fase` bloqueia a linha do lead. Cada mudança real para `REUNIAO_MARCADA` insere uma reunião `AGENDADA` com `criado_em` e `data_reuniao` obtidos do relógio PostgreSQL. O campo obrigatório de data prevista recebe a hora da entrada; o agendamento manual continua aceitando uma data prevista específica.
- Fase, primeira prospecção, histórico produzido pelo trigger existente e reunião são gravados no mesmo commit. Qualquer falha desfaz a transação.
- Repetir a mesma fase não insere reunião. Sair e retornar insere outra reunião.
- Reuniões existentes permanecem intactas. Não são inferidos agendamentos a partir de movimentações antigas, evitando duplicidade ou contagens retroativas sem conciliação.
- Os indicadores mensal e `/metas/dashboard` compartilham a mesma consulta por `reunioes.criado_em`, com os status já utilizados (`AGENDADA`, `REALIZADA`). A data prevista não define o mês da contagem.

## Exclusão e fechamento

O banco atual possui FK do histórico com `ON DELETE CASCADE` e FK das reuniões que impede remover leads vinculados. Por isso, exclusão e fechamento agora arquivam o lead (`arquivado_em`) em vez de removê-lo fisicamente.

Leads arquivados não aparecem em `GET /leads`, não podem ser movimentados, editados, excluídos novamente nem receber novos agendamentos. Seus registros de prospecção, histórico e reuniões continuam disponíveis e contáveis. No fechamento, o cliente novo recebe `lead_id`, preservando a origem e impedindo conversões repetidas. Nenhuma FK é desativada.

Não foi possível recuperar registros já apagados por exclusões físicas anteriores; esta mudança protege as operações futuras.

## Validação

Em `backend`, executar:

```powershell
../.venv/Scripts/python.exe -m unittest test_prospeccoes test_reunioes -v
```

Os 12 testes usam schemas PostgreSQL temporários isolados e removem apenas seus próprios dados. Cobrem primeira prospecção, reuniões por entrada, repetição, retorno, consultas repetidas, concorrência, rollback, competência mensal, preservação após conversão/exclusão e consistência das consultas usadas por Metas e Dashboard. Os registros reais não são movimentados pelos testes.
