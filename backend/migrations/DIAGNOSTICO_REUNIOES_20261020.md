# Divergência de reuniões — 20/10/2026

Consulta somente de leitura no banco local, período outubro/2026:

- Kanban atual: três leads em FOLLOW_UP, nenhum em REUNIAO_MARCADA.
- Histórico: seis entradas em REUNIAO_MARCADA (IDs 2, 8, 12, 14, 18, 27), entre 06 e 16/10.
- Tabela reunioes: um agendamento criado em 13/10, com realização prevista para 20/10.
- Não há correspondência de data de criação entre esse agendamento e as seis transições.
- `/reunioes/indicadores/mensal` e `/metas/dashboard` retornam uma reunião, usando a mesma função `contar_reunioes_mensais`.

A posição atual dos cards não desfaz agendamentos passados. Entrar novamente em REUNIAO_MARCADA cria outro agendamento; repetir a mesma fase não cria registro. Os testes de transição, concorrência, rollback, conversão, exclusão e competência mensal passaram.

Não foram criados registros retroativos: é necessário confirmar quais movimentações antigas representam agendamentos reais e se a reunião cadastrada separadamente corresponde a algum deles. Somar os sete registros automaticamente pode duplicar um agendamento real. Uma recuperação deve manter as datas históricas, ser idempotente e preservar o agendamento existente.

O Dashboard passou a atualizar suas consultas a cada dez segundos quando visível e ao voltar à aba ou recuperar conexão, como a página Metas. A página Metas recebeu uma explicação do critério de contagem. Nenhuma meta, reunião ou movimentação real foi alterada.
