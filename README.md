# CRM ART X

CRM desenvolvido do zero para apoiar a operação comercial e a gestão de
projetos da **ART X**, uma agência de marketing.

O projeto está sendo construído como uma aplicação full stack, com foco
em **CRM, automação de processos comerciais, gestão de clientes,
acompanhamento de metas e organização de projetos**.

> **Status:** em desenvolvimento --- banco de dados inicial concluído e
> backend em preparação.

------------------------------------------------------------------------

## Sobre o projeto

O CRM ART X foi pensado para centralizar o fluxo comercial da agência,
desde a identificação de empresas que ainda serão prospectadas até a
conversão em clientes e o acompanhamento dos projetos contratados.

O sistema contará com cinco áreas principais:

-   **Leads** --- funil comercial em Kanban;
-   **Clientes** --- gestão da carteira e faturamento recorrente;
-   **Projetos** --- Kanban de execução e checklists;
-   **Metas** --- acompanhamento mensal de prospecções, reuniões e novos
    faturamentos;
-   **Configurações** --- usuários e preferências do sistema.

Também haverá uma **tela de login**, com autenticação de usuários e
gerenciamento de acessos pelo administrador.

------------------------------------------------------------------------

## Fluxo comercial

O Kanban de leads utiliza quatro fases:

``` text
PROSPECTAR
    ↓
FOLLOW_UP
    ↓
REUNIAO_MARCADA

ou

REMARKETING_FUTURO
```

### Regra de prospecção

Um lead em `PROSPECTAR` representa uma empresa que **ainda não foi
prospectada**.

A prospecção passa a ser contabilizada quando o lead sai dessa etapa
para:

-   `FOLLOW_UP`;
-   `REUNIAO_MARCADA`;
-   `REMARKETING_FUTURO`.

As movimentações são armazenadas automaticamente no histórico do lead,
permitindo gerar métricas comerciais por período.

------------------------------------------------------------------------

## Clientes e faturamento

Quando um lead fecha contrato, ele pode ser convertido em cliente.

Cada cliente possui um `valor_mensal`, permitindo acompanhar dois
indicadores diferentes:

**Faturamento mensal atual**

Soma das mensalidades de todos os clientes ativos.

**Novos faturamentos**

Soma das mensalidades dos clientes que iniciaram contrato no mês
analisado.

Exemplo:

``` text
Outubro
Cliente A → R$ 1.000

Faturamento atual:   R$ 1.000
Novos faturamentos: R$ 1.000

Novembro
Cliente B → R$ 500

Faturamento atual:   R$ 1.500
Novos faturamentos: R$   500
```

Clientes encerrados são mantidos no banco como inativos para preservar o
histórico.

------------------------------------------------------------------------

## Gestão de projetos

Cada projeto é associado a um cliente e possui:

-   nome;
-   prazo;
-   prioridade;
-   status;
-   observações;
-   checklist personalizado.

O Kanban de projetos possui as etapas:

``` text
PENDENTE
EM_ANDAMENTO
FINALIZADA
```

Os itens do checklist são criados manualmente para cada projeto.

------------------------------------------------------------------------

## Metas

As metas são configuradas individualmente para cada mês.

Os três indicadores são fixos:

``` text
Meta de prospecções
Meta de reuniões
Meta de faturamento
```

Os valores realizados não precisam ser preenchidos manualmente.

O CRM calcula automaticamente:

-   quantidade de leads prospectados;
-   quantidade de leads que chegaram a reunião;
-   novos faturamentos;
-   percentual de atingimento de cada meta.

------------------------------------------------------------------------

## Usuários e autenticação

Todos os usuários terão acesso às funcionalidades operacionais do CRM.

Existirão dois tipos:

``` text
ADMIN
USUARIO
```

O administrador terá uma permissão adicional: **cadastrar novos
usuários**.

As senhas não serão armazenadas em texto puro. O backend armazenará
somente hashes seguros.

------------------------------------------------------------------------

## Arquitetura planejada

``` text
┌──────────────────────────┐
│         Frontend         │
│     React / Next.js      │
└────────────┬─────────────┘
             │
             │ HTTP / API
             ▼
┌──────────────────────────┐
│          Backend         │
│          FastAPI         │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│        SQLAlchemy        │
│           ORM            │
└────────────┬─────────────┘
             │
             ▼
┌──────────────────────────┐
│        PostgreSQL        │
│         CRM_artX         │
└──────────────────────────┘
```

O frontend não acessará o banco diretamente. Toda comunicação com o
PostgreSQL será realizada através da API.

------------------------------------------------------------------------

## Banco de dados

A primeira versão do banco possui sete tabelas:

``` text
CRM_artX
│
├── leads
├── historico_leads
├── clientes
├── projetos
├── checklist_items
├── metas
└── usuarios
```

Principais relacionamentos:

``` text
LEADS
  │
  ├──────────> HISTORICO_LEADS
  │
  ▼
CLIENTES
  │
  ▼
PROJETOS
  │
  ▼
CHECKLIST_ITEMS

METAS
USUARIOS
```

A modelagem utiliza:

-   Primary Keys;
-   Foreign Keys;
-   constraints `CHECK`;
-   constraints `UNIQUE`;
-   triggers;
-   funções PL/pgSQL;
-   integridade referencial;
-   timestamps automáticos;
-   histórico de movimentações.

A documentação detalhada está disponível em:

``` text
docs/database.md
```

------------------------------------------------------------------------

## Tecnologias

### Banco de dados

-   PostgreSQL
-   pgAdmin 4
-   SQL / PL/pgSQL

### Backend

Planejado:

-   Python
-   FastAPI
-   SQLAlchemy

### Frontend

Planejado:

-   React
-   Next.js

------------------------------------------------------------------------

## Estrutura planejada do repositório

``` text
artx-crm/
│
├── backend/
│   ├── app/
│   ├── tests/
│   └── requirements.txt
│
├── frontend/
│
├── database/
│   ├── schema.sql
│   ├── triggers.sql
│   └── seed.sql
│
├── docs/
│   ├── database.md
│   ├── backend.md
│   └── architecture.md
│
├── .env.example
├── .gitignore
└── README.md
```

------------------------------------------------------------------------

## Status do desenvolvimento

### Banco de dados

-   [x] Modelagem inicial
-   [x] Leads
-   [x] Histórico de movimentações
-   [x] Clientes
-   [x] Projetos
-   [x] Checklists
-   [x] Metas mensais
-   [x] Usuários
-   [x] Triggers
-   [x] Integridade referencial
-   [x] Métricas de prospecção
-   [x] Métricas de reuniões
-   [x] Métricas de faturamento
-   [x] Percentual de atingimento das metas

### Backend

-   [ ] Estrutura Python
-   [ ] Conexão PostgreSQL
-   [ ] SQLAlchemy
-   [ ] FastAPI
-   [ ] Endpoints
-   [ ] Autenticação
-   [ ] Autorização
-   [ ] Testes

### Frontend

-   [ ] Login
-   [ ] Leads
-   [ ] Clientes
-   [ ] Projetos
-   [ ] Metas
-   [ ] Configurações
-   [ ] Tema claro/escuro
-   [ ] Integração com API

### Infraestrutura

-   [ ] Variáveis de ambiente
-   [ ] Deploy do backend
-   [ ] Deploy do frontend
-   [ ] Banco em ambiente de produção

------------------------------------------------------------------------

## Próxima etapa

A próxima fase do desenvolvimento é a construção do backend:

``` text
Python
   ↓
FastAPI
   ↓
SQLAlchemy
   ↓
PostgreSQL
   ↓
Endpoints REST
   ↓
Autenticação
```

------------------------------------------------------------------------

## Documentação

Para detalhes sobre tabelas, relacionamentos, regras de negócio,
triggers e consultas do banco:

➡️ [`docs/database.md`](docs/database.md)

------------------------------------------------------------------------

## Observação

O **CRM ART X** está em desenvolvimento. A arquitetura, documentação e
funcionalidades serão atualizadas conforme a evolução do projeto.
