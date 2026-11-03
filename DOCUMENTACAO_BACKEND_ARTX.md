# ART X CRM — Documentação do Backend e API

> **Estado do projeto:** backend em desenvolvimento, com endpoints principais testados localmente pelo Swagger. Este documento descreve o que foi implementado e validado até outubro de 2026; não equivale a uma auditoria integral do código-fonte.

## 1. Visão geral

O **ART X CRM** é um sistema de gestão comercial e de projetos para a agência ART X. O backend centraliza leads, clientes, contratos recorrentes, projetos, checklists, metas e reuniões. A interface web (frontend) será desenvolvida em etapa posterior.

### Tecnologias

| Camada | Tecnologia |
| --- | --- |
| Linguagem | Python 3.13 |
| API | FastAPI |
| Servidor de desenvolvimento | Uvicorn |
| ORM | SQLAlchemy |
| Validação de dados | Pydantic |
| Banco de dados | PostgreSQL 18 |
| Administração do banco | pgAdmin 4 |
| Testes manuais da API | Swagger UI (`/docs`) |

## 2. Organização do projeto

Estrutura de arquivos conhecida até o momento:

```text
artx-crm/
├── .venv/                 # Ambiente virtual local (não versionar)
└── backend/
    ├── main.py            # Rotas e regras de negócio da API
    ├── database.py        # Conexão com PostgreSQL e sessão SQLAlchemy
    ├── models.py          # Modelos ORM
    └── schemas.py         # Schemas de entrada/validação Pydantic
```

A existência de outros arquivos (por exemplo, `requirements.txt`, `.env` ou testes automatizados) deve ser verificada no repositório antes de documentá-los como concluídos.

## 3. Modelo funcional

### Leads

Fluxo Kanban planejado:

1. `PROSPECTAR`
2. `FOLLOW_UP`
3. `REUNIAO_MARCADA`
4. `REMARKETING_FUTURO`

Dados básicos: empresa, nicho, telefone, e-mail, fase e observações. O banco mantém histórico de movimentações entre fases.

**Regra de prospecção:** cada lead conta **uma única vez**, na primeira prospecção registrada. A coluna `leads.prospectado_em` armazena o instante da primeira prospecção. Novas tentativas não aumentam a contagem.

### Clientes e receita recorrente

Cada cliente possui valor mensal de contrato, data de início, data de encerramento (quando aplicável) e status `ATIVO` ou `INATIVO`.

- **Faturamento recorrente mensal:** soma dos valores mensais dos contratos vigentes no fechamento do mês consultado.
- **Novos faturamentos:** indicador conceitualmente distinto, referente aos contratos iniciados no mês; não deve ser confundido com o total recorrente.
- O cálculo de faturamento recorrente implementado utiliza **datas de vigência** para permitir consultas históricas, em vez de depender apenas do status atual.
- Não é um relatório de pagamentos efetivamente recebidos nem faz rateio proporcional de mensalidades.

### Projetos e checklists

Projetos associados a clientes, com nome, prazo, prioridade, status e observações. Cada projeto pode possuir itens de checklist com estado de conclusão. Os estados utilizados são `PENDENTE`, `EM_ANDAMENTO` e `FINALIZADA`; prioridades incluem `BAIXA`, `MEDIA`, `ALTA` e `URGENTE`.

### Reuniões

Cada agendamento é armazenado como um registro próprio na tabela `reunioes`, mesmo quando o mesmo lead já teve reuniões anteriores.

Campos principais: `lead_id`, `data_reuniao`, `status`, `observacao` e `criado_em`. Status previstos: `AGENDADA`, `REALIZADA`, `CANCELADA`.

**Regra do indicador:** contabilizar reuniões criadas no mês (`criado_em`) com status `AGENDADA` ou `REALIZADA`; reuniões `CANCELADA` ficam fora da contagem de agendamentos válidos. A data efetiva da reunião (`data_reuniao`) não define o mês do indicador.

### Metas mensais

Cada competência (ano/mês) tem metas configuráveis de:

- Quantidade de leads prospectados;
- Quantidade de reuniões agendadas válidas;
- Faturamento recorrente.

Os indicadores de progresso retornam meta, realizado, quantidade/valor faltante e percentual atingido.

## 4. Endpoints implementados e testados

A tabela abaixo reúne as **rotas confirmadas na evolução do projeto**. Outros endpoints de CRUD de leads, clientes, projetos, checklists e metas foram construídos/testados, mas suas URLs e métodos exatos devem ser conferidos no Swagger antes de serem listados como contrato definitivo.

| Método | Rota | Finalidade |
| --- | --- | --- |
| `PATCH` | `/leads/{lead_id}/prospectar` | Registra a primeira prospecção de um lead, sem duplicar contagem |
| `GET` | `/leads/prospeccoes/mensal` | Consulta total de leads prospectados no mês |
| `POST` | `/reunioes` | Cria agendamento associado a um lead |
| `GET` | `/reunioes/indicadores/mensal` | Conta reuniões agendadas válidas no mês |
| `GET` | `/metas/progresso/prospeccoes` | Progresso da meta de prospecções |
| `GET` | `/metas/progresso/reunioes` | Progresso da meta de reuniões |
| `GET` | `/metas/progresso/faturamento` | Progresso da meta de receita recorrente |
| `GET` | `/metas/dashboard` | Consolida os três indicadores de metas |

### Parâmetros das consultas mensais

As rotas de consulta mensal recebem:

| Parâmetro | Tipo | Exemplo |
| --- | --- | --- |
| `ano` | Inteiro | `2026` |
| `mes` | Inteiro, 1 a 12 | `10` |

Exemplo de chamada local:

```http
GET http://127.0.0.1:8000/metas/dashboard?ano=2026&mes=10
```

### Exemplo: criar reunião

```http
POST /reunioes
Content-Type: application/json
```

```json
{
  "lead_id": 1,
  "data_reuniao": "2026-10-20T14:00:00",
  "observacao": "Apresentação da proposta comercial"
}
```

Resposta observada: `201 Created`, com identificador da reunião, lead associado, data, status inicial `AGENDADA` e observação.

### Exemplo: registrar prospecção

```http
PATCH /leads/1/prospectar
```

Na primeira chamada, `contabilizado_agora` é `true`; nas seguintes, `false`, mantendo a data da primeira prospecção.

## 5. Dashboard de metas — formato de resposta

Exemplo **de dados de teste locais**, não dados reais de produção:

```json
{
  "ano": 2026,
  "mes": 10,
  "prospeccoes": {
    "ano": 2026,
    "mes": 10,
    "meta_prospeccoes": 300,
    "prospeccoes_realizadas": 1,
    "faltam": 299,
    "percentual_atingido": 0.33
  },
  "reunioes": {
    "ano": 2026,
    "mes": 10,
    "meta_reunioes": 30,
    "reunioes_realizadas": 1,
    "faltam": 29,
    "percentual_atingido": 3.33
  },
  "faturamento": {
    "ano": 2026,
    "mes": 10,
    "meta_faturamento": 20000,
    "faturamento_recorrente": 1000,
    "faltam": 19000,
    "percentual_atingido": 5
  }
}
```

> **Nota de nomenclatura:** o campo `reunioes_realizadas` na rota de progresso representa, na implementação atual, **agendamentos válidos** (`AGENDADA` + `REALIZADA`), não exclusivamente reuniões que ocorreram. Recomenda-se renomeá-lo futuramente para `reunioes_agendadas` e alinhar o contrato da API com o frontend.

## 6. Cálculos e critérios de negócio

### Prospecções

```text
Realizado = quantidade de leads com prospectado_em dentro do mês
Percentual = (realizado / meta) × 100, se meta > 0
Faltam = máximo(meta − realizado, 0)
```

### Reuniões

```text
Realizado = quantidade de reuniões criadas no mês
            com status AGENDADA ou REALIZADA
Percentual = (realizado / meta) × 100, se meta > 0
Faltam = máximo(meta − realizado, 0)
```

### Faturamento

A consulta atual soma `clientes.valor_mensal` quando:

- `data_inicio` é anterior ao primeiro dia do mês seguinte; e
- `data_encerramento` está vazia ou é igual/posterior ao primeiro dia do mês seguinte.

Isso corresponde a contratos ainda vigentes **no encerramento do mês**. Contratos encerrados dentro do mês não entram no valor recorrente do fechamento. Para um painel operacional do mês corrente, vale decidir futuramente se também será necessário um indicador de receita vigente **hoje**.

## 7. Validações manuais realizadas

Os testes abaixo foram realizados localmente via Swagger e pgAdmin:

| Teste | Resultado |
| --- | --- |
| Registro da primeira prospecção de um lead | `200 OK`, contabilização uma única vez |
| Repetição da mesma prospecção | `200 OK`, sem contagem duplicada |
| Total de prospecções de outubro/2026 | `1` |
| Progresso da meta de prospecções (1/300) | `0,33%` |
| Cadastro de reunião | `201 Created` |
| Persistência da reunião no PostgreSQL | Confirmada no pgAdmin |
| Total de reuniões de outubro/2026 | `1` |
| Progresso da meta de reuniões (1/30) | `3,33%` |
| Progresso da meta de faturamento (R$ 1.000/R$ 20.000) | `5%` |
| Dashboard consolidado | `200 OK`, três indicadores retornados |

Esses são testes manuais de integração. Não foi confirmada a existência de uma suíte automatizada.

## 8. Como executar localmente

No Windows, a partir da raiz do projeto:

```powershell
cd C:\Users\SIMONE\Documents\artx-crm
.\.venv\Scripts\Activate.ps1
cd backend
uvicorn main:app --reload
```

A API poderá ser acessada em:

- Documentação interativa: http://127.0.0.1:8000/docs
- Especificação OpenAPI: http://127.0.0.1:8000/openapi.json

**Pré-requisitos:** PostgreSQL em execução, banco `CRM_artX` existente, tabelas criadas e conexão configurada em `database.py`. Os comandos exatos de instalação de dependências dependem de um arquivo de dependências a ser confirmado/criado no repositório.

## 9. Boas práticas para publicar no GitHub

- Versionar código-fonte, documentação e scripts de criação/migração do banco.
- **Não versionar:** `.venv/`, `.env`, senhas, tokens, credenciais do banco, arquivos temporários e caches Python.
- Criar um `.env.example` com nomes de variáveis, sem valores secretos.
- Gerar e revisar `requirements.txt` para reproduzir o ambiente.
- Adicionar instruções de instalação e migração do banco ao `README.md`.
- Evitar publicar dados pessoais de leads e clientes; utilizar registros fictícios nos exemplos.

Exemplo mínimo de `.gitignore`:

```gitignore
.venv/
.env
__pycache__/
*.py[cod]
.pytest_cache/
.vscode/
```

## 10. Próximas etapas

1. Revisar e padronizar contratos de resposta e nomes dos campos da API.
2. Completar endpoints de listagem, edição e cancelamento de reuniões, se ainda não existentes.
3. Implementar autenticação e controle de usuários/permissões.
4. Adicionar testes automatizados e tratamento consistente de erros.
5. Configurar CORS de forma restrita para o frontend.
6. Criar interface React/Next.js para Dashboard, Leads, Clientes, Projetos, Metas e Configurações.
7. Preparar deploy e configuração segura de ambiente.

---

**Projeto:** ART X CRM  
**Documento:** Backend e API — documentação técnica e funcional  
**Referência:** outubro de 2026
