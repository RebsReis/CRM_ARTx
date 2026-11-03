# Banco de Dados --- CRM ART X

## 1. Visão geral

O banco de dados do **CRM ART X** foi desenvolvido em **PostgreSQL**
para sustentar as principais operações comerciais e de gestão da
agência.

Nesta primeira versão (MVP), o banco atende aos módulos de:

-   Leads;
-   Clientes;
-   Projetos;
-   Metas;
-   Usuários e autenticação.

Além das entidades principais, existem estruturas auxiliares para
registrar o histórico de movimentações dos leads e os itens de checklist
de cada projeto.

**Banco utilizado no desenvolvimento:** `CRM_artX`

### Estrutura atual

``` text
CRM_artX
├── leads
├── historico_leads
├── clientes
├── projetos
├── checklist_items
├── metas
└── usuarios
```

------------------------------------------------------------------------

## 2. Modelo lógico e relacionamentos

Os principais relacionamentos do banco são:

``` text
LEADS
  │
  ├── 1:N ──> HISTORICO_LEADS
  │
  └── 0..1:0..1 ──> CLIENTES
                         │
                         └── 1:N ──> PROJETOS
                                        │
                                        └── 1:N ──> CHECKLIST_ITEMS

METAS       → metas mensais da operação comercial
USUARIOS    → autenticação e controle do administrador
```

### Resumo

  Origem       Destino             Relacionamento   Chave
  ------------ ------------------- ---------------- ------------------------------
  `leads`      `historico_leads`   1:N              `historico_leads.lead_id`
  `leads`      `clientes`          0..1:0..1        `clientes.lead_id`
  `clientes`   `projetos`          1:N              `projetos.cliente_id`
  `projetos`   `checklist_items`   1:N              `checklist_items.projeto_id`

------------------------------------------------------------------------

## 3. Tabela `leads`

Representa as empresas que fazem parte do processo comercial da ART X.

### Estrutura

``` sql
CREATE TABLE leads (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    nome_empresa VARCHAR(150) NOT NULL,
    nicho VARCHAR(100),
    telefone VARCHAR(30),
    email VARCHAR(150),

    fase VARCHAR(30) NOT NULL DEFAULT 'PROSPECTAR'
        CHECK (
            fase IN (
                'PROSPECTAR',
                'FOLLOW_UP',
                'REUNIAO_MARCADA',
                'REMARKETING_FUTURO'
            )
        ),

    observacao TEXT,

    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Campos

  Campo             Descrição
  ----------------- -------------------------------
  `id`              Identificador único
  `nome_empresa`    Nome da empresa
  `nicho`           Segmento de atuação
  `telefone`        Telefone de contato
  `email`           E-mail de contato
  `fase`            Fase atual do funil comercial
  `observacao`      Observações livres
  `criado_em`       Data/hora de criação
  `atualizado_em`   Data/hora da última alteração

### Fases do funil

-   `PROSPECTAR`: empresa cadastrada, mas ainda não prospectada;
-   `FOLLOW_UP`: empresa já prospectada e aguardando nova interação;
-   `REUNIAO_MARCADA`: empresa prospectada com reunião marcada;
-   `REMARKETING_FUTURO`: empresa já prospectada que deverá ser abordada
    novamente no futuro.

**Regra de negócio:** permanecer em `PROSPECTAR` não conta como
prospecção realizada.

------------------------------------------------------------------------

## 4. Tabela `historico_leads`

Registra as mudanças de fase dos leads para permitir rastreabilidade e
cálculo de indicadores por período.

### Estrutura

``` sql
CREATE TABLE historico_leads (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    lead_id BIGINT NOT NULL,

    fase_anterior VARCHAR(30),
    fase_nova VARCHAR(30) NOT NULL,

    movimentado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_historico_lead
        FOREIGN KEY (lead_id)
        REFERENCES leads(id)
        ON DELETE CASCADE
);
```

### Exemplo de histórico

``` text
PROSPECTAR → FOLLOW_UP
FOLLOW_UP → REUNIAO_MARCADA
```

O histórico permite saber **quando** uma movimentação ocorreu, em vez de
armazenar apenas a fase atual do lead.

------------------------------------------------------------------------

## 5. Trigger de histórico de leads

A movimentação é registrada automaticamente quando o campo `fase` é
alterado.

``` sql
CREATE OR REPLACE FUNCTION registrar_historico_lead()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.fase IS DISTINCT FROM NEW.fase THEN

        INSERT INTO historico_leads (
            lead_id,
            fase_anterior,
            fase_nova,
            movimentado_em
        )
        VALUES (
            OLD.id,
            OLD.fase,
            NEW.fase,
            CURRENT_TIMESTAMP
        );

    END IF;

    NEW.atualizado_em = CURRENT_TIMESTAMP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

``` sql
CREATE TRIGGER trigger_historico_lead
BEFORE UPDATE ON leads
FOR EACH ROW
EXECUTE FUNCTION registrar_historico_lead();
```

Com isso, o backend precisa alterar apenas a fase do lead. O PostgreSQL
registra o histórico automaticamente.

------------------------------------------------------------------------

## 6. Regra de contabilização de prospecções

Um lead em `PROSPECTAR` ainda representa uma ação comercial futura.

Uma prospecção é considerada realizada quando o lead **sai de
`PROSPECTAR`** para uma das seguintes fases:

``` text
FOLLOW_UP
REUNIAO_MARCADA
REMARKETING_FUTURO
```

Exemplo:

``` text
PROSPECTAR → FOLLOW_UP
```

Resultado:

``` text
+1 prospecção realizada
```

Se posteriormente ocorrer:

``` text
FOLLOW_UP → REUNIAO_MARCADA
```

o mesmo lead não passa a representar duas prospecções. Ele continua
representando uma prospecção e passa a contribuir também para o
indicador de reunião.

As consultas analíticas utilizam `COUNT(DISTINCT lead_id)` para evitar
duplicidades dentro do período analisado.

------------------------------------------------------------------------

## 7. Tabela `clientes`

Armazena os clientes da agência e sua receita mensal recorrente.

Um cliente pode ser originado da conversão de um lead ou cadastrado
diretamente.

### Estrutura

``` sql
CREATE TABLE clientes (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    lead_id BIGINT UNIQUE,

    nome_empresa VARCHAR(150) NOT NULL,
    nicho VARCHAR(100),
    telefone VARCHAR(30),
    email VARCHAR(150),

    valor_mensal NUMERIC(12,2) NOT NULL
        CHECK (valor_mensal >= 0),

    data_inicio DATE NOT NULL DEFAULT CURRENT_DATE,
    data_encerramento DATE,

    status VARCHAR(20) NOT NULL DEFAULT 'ATIVO'
        CHECK (status IN ('ATIVO', 'INATIVO')),

    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_cliente_lead
        FOREIGN KEY (lead_id)
        REFERENCES leads(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_datas_cliente
        CHECK (
            data_encerramento IS NULL
            OR data_encerramento >= data_inicio
        )
);
```

O `lead_id` é opcional, permitindo cadastrar clientes que não passaram
previamente pelo funil de leads.

------------------------------------------------------------------------

## 8. Regras de faturamento

O CRM diferencia dois indicadores.

### 8.1 Faturamento mensal atual

É a soma do `valor_mensal` de todos os clientes atualmente ativos.

Exemplo:

``` text
Cliente A = R$ 1.000/mês
Cliente B = R$   500/mês

Faturamento mensal atual = R$ 1.500
```

Um cliente permanece nesse total enquanto estiver ativo.

### 8.2 Novos faturamentos

É a soma dos valores mensais dos clientes cuja `data_inicio` pertence ao
mês analisado.

Exemplo:

``` text
Outubro
Cliente A entra com R$ 1.000

Faturamento atual:   R$ 1.000
Novos faturamentos: R$ 1.000

Novembro
Cliente B entra com R$ 500

Faturamento atual:   R$ 1.500
Novos faturamentos: R$   500

Dezembro
Nenhum novo cliente

Faturamento atual:   R$ 1.500
Novos faturamentos: R$     0
```

### 8.3 Encerramento

Clientes que deixam a agência devem ser preferencialmente encerrados, e
não excluídos fisicamente:

``` text
status = INATIVO
data_encerramento = <data>
```

Isso preserva o histórico e permitirá análises futuras de churn,
retenção e receita.

------------------------------------------------------------------------

## 9. Tabela `projetos`

Cada projeto pertence obrigatoriamente a um cliente.

### Estrutura

``` sql
CREATE TABLE projetos (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cliente_id BIGINT NOT NULL,

    nome_projeto VARCHAR(200) NOT NULL,

    prazo DATE,

    prioridade VARCHAR(20) NOT NULL DEFAULT 'MEDIA'
        CHECK (
            prioridade IN (
                'BAIXA',
                'MEDIA',
                'ALTA',
                'URGENTE'
            )
        ),

    status VARCHAR(30) NOT NULL DEFAULT 'PENDENTE'
        CHECK (
            status IN (
                'PENDENTE',
                'EM_ANDAMENTO',
                'FINALIZADA'
            )
        ),

    observacao TEXT,

    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_projeto_cliente
        FOREIGN KEY (cliente_id)
        REFERENCES clientes(id)
);
```

### Status do Kanban

``` text
PENDENTE
EM_ANDAMENTO
FINALIZADA
```

### Prioridades

``` text
BAIXA
MEDIA
ALTA
URGENTE
```

As restrições `CHECK` impedem que valores fora dos domínios definidos
sejam armazenados.

------------------------------------------------------------------------

## 10. Tabela `checklist_items`

Cada projeto pode possuir um checklist próprio e variável.

### Estrutura

``` sql
CREATE TABLE checklist_items (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    projeto_id BIGINT NOT NULL,

    descricao VARCHAR(255) NOT NULL,

    concluido BOOLEAN NOT NULL DEFAULT FALSE,

    ordem INTEGER NOT NULL DEFAULT 0,

    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    concluido_em TIMESTAMP,

    CONSTRAINT fk_checklist_projeto
        FOREIGN KEY (projeto_id)
        REFERENCES projetos(id)
        ON DELETE CASCADE
);
```

Não existem itens padrão obrigatórios. Cada projeto pode possuir zero ou
vários itens, criados manualmente.

`ON DELETE CASCADE` garante que os itens do checklist sejam removidos
caso o respectivo projeto seja excluído.

------------------------------------------------------------------------

## 11. Tabela `metas`

Armazena as metas comerciais mensais.

Os indicadores são sempre os mesmos:

1.  Meta de prospecções;
2.  Meta de reuniões;
3.  Meta de faturamento.

Os **valores** podem ser diferentes para cada mês.

### Estrutura

``` sql
CREATE TABLE metas (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ano INTEGER NOT NULL,
    mes INTEGER NOT NULL
        CHECK (mes BETWEEN 1 AND 12),

    meta_prospeccoes INTEGER NOT NULL DEFAULT 0
        CHECK (meta_prospeccoes >= 0),

    meta_reunioes INTEGER NOT NULL DEFAULT 0
        CHECK (meta_reunioes >= 0),

    meta_faturamento NUMERIC(12,2) NOT NULL DEFAULT 0
        CHECK (meta_faturamento >= 0),

    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_meta_mes UNIQUE (ano, mes)
);
```

A restrição:

``` sql
UNIQUE (ano, mes)
```

impede a existência de duas configurações concorrentes de metas para o
mesmo mês.

------------------------------------------------------------------------

## 12. Meta x realizado

O banco armazena as **metas**, mas os valores realizados são derivados
dos dados operacionais.

### Prospecções realizadas

Conta os leads distintos que saíram de `PROSPECTAR` no período para:

-   `FOLLOW_UP`;
-   `REUNIAO_MARCADA`;
-   `REMARKETING_FUTURO`.

### Reuniões realizadas

Conta os leads distintos que entraram em `REUNIAO_MARCADA` durante o
período.

### Faturamento realizado da meta

Soma o `valor_mensal` dos clientes cuja `data_inicio` pertence ao mês
analisado.

Portanto, a meta de faturamento é comparada aos **novos faturamentos**,
e não à receita recorrente total da agência.

### Exemplo validado durante o desenvolvimento

``` text
Prospecções
Meta: 150
Realizado: 1
Percentual: 0,67%

Reuniões
Meta: 25
Realizado: 1
Percentual: 4,00%

Faturamento
Meta: R$ 15.000
Realizado: R$ 1.000
Percentual: 6,67%
```

------------------------------------------------------------------------

## 13. Tabela `usuarios`

Suporta a futura tela de login e o gerenciamento de usuários.

### Estrutura

``` sql
CREATE TABLE usuarios (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    nome VARCHAR(150) NOT NULL,

    email VARCHAR(150) NOT NULL UNIQUE,

    senha_hash VARCHAR(255) NOT NULL,

    tipo VARCHAR(20) NOT NULL DEFAULT 'USUARIO'
        CHECK (
            tipo IN (
                'ADMIN',
                'USUARIO'
            )
        ),

    ativo BOOLEAN NOT NULL DEFAULT TRUE,

    criado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

### Perfis

-   `ADMIN`: possui acesso ao CRM e pode cadastrar novos usuários;
-   `USUARIO`: possui acesso às funcionalidades do CRM, mas não pode
    cadastrar usuários.

A regra funcional prevê apenas um administrador principal.

> **Nota:** a estrutura atual aceita tecnicamente mais de um registro
> `ADMIN`. A garantia de um único administrador ainda deverá ser
> implementada na aplicação ou, se desejado, por uma restrição adicional
> no PostgreSQL.

------------------------------------------------------------------------

## 14. Segurança de senhas

Senhas **não devem ser armazenadas em texto puro**.

O campo:

``` text
senha_hash
```

armazenará apenas o hash produzido pelo backend.

Fluxo planejado:

``` text
Usuário informa e-mail + senha
            │
            ▼
          FastAPI
            │
            ├── busca usuário pelo e-mail
            ├── verifica se está ativo
            └── compara senha com o hash
            │
            ▼
       autenticação
```

Credenciais, senhas do PostgreSQL e segredos da aplicação não devem ser
versionados no GitHub.

------------------------------------------------------------------------

## 15. Atualização automática de timestamps

Foi criada uma função reutilizável para atualizar `atualizado_em`:

``` sql
CREATE OR REPLACE FUNCTION atualizar_data_modificacao()
RETURNS TRIGGER AS $$
BEGIN
    NEW.atualizado_em = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

Ela foi associada às tabelas:

-   `clientes`;
-   `projetos`;
-   `metas`;
-   `usuarios`.

``` sql
CREATE TRIGGER trigger_atualizar_clientes
BEFORE UPDATE ON clientes
FOR EACH ROW
EXECUTE FUNCTION atualizar_data_modificacao();

CREATE TRIGGER trigger_atualizar_projetos
BEFORE UPDATE ON projetos
FOR EACH ROW
EXECUTE FUNCTION atualizar_data_modificacao();

CREATE TRIGGER trigger_atualizar_metas
BEFORE UPDATE ON metas
FOR EACH ROW
EXECUTE FUNCTION atualizar_data_modificacao();

CREATE TRIGGER trigger_atualizar_usuarios
BEFORE UPDATE ON usuarios
FOR EACH ROW
EXECUTE FUNCTION atualizar_data_modificacao();
```

A tabela `leads` atualiza esse campo por meio do próprio trigger
`registrar_historico_lead`.

------------------------------------------------------------------------

## 16. Integridade referencial

### `historico_leads → leads`

``` text
historico_leads.lead_id → leads.id
```

Usa `ON DELETE CASCADE`, pois um histórico não deve existir sem seu
lead.

### `clientes → leads`

``` text
clientes.lead_id → leads.id
```

Usa `ON DELETE SET NULL`, permitindo preservar o cliente mesmo que a
referência ao lead seja removida.

### `projetos → clientes`

``` text
projetos.cliente_id → clientes.id
```

Um projeto deve pertencer a um cliente.

### `checklist_items → projetos`

``` text
checklist_items.projeto_id → projetos.id
```

Usa `ON DELETE CASCADE`.

------------------------------------------------------------------------

## 17. Dados de desenvolvimento

Durante a validação inicial foram utilizados dados fictícios, incluindo:

-   Lead: Nike;
-   Fluxo: `PROSPECTAR → FOLLOW_UP → REUNIAO_MARCADA`;
-   Cliente de teste: R\$ 1.000/mês;
-   Projeto: `Campanha Black Friday`;
-   Itens de checklist fictícios.

Esses registros servem apenas para desenvolvimento e validação da
modelagem e não representam dados reais da operação.

------------------------------------------------------------------------

## 18. Divisão de responsabilidades da aplicação

A arquitetura planejada é:

``` text
┌────────────────────────┐
│        Frontend        │
│    React / Next.js     │
└───────────┬────────────┘
            │ HTTP / API
            ▼
┌────────────────────────┐
│         Backend        │
│        FastAPI         │
└───────────┬────────────┘
            │
            ▼
┌────────────────────────┐
│       SQLAlchemy       │
│          ORM           │
└───────────┬────────────┘
            │ SQL
            ▼
┌────────────────────────┐
│       PostgreSQL       │
│        CRM_artX        │
└────────────────────────┘
```

### PostgreSQL

Responsável por:

-   persistência;
-   relacionamentos;
-   integridade referencial;
-   restrições;
-   histórico de movimentações;
-   timestamps;
-   consultas e agregações.

### FastAPI / backend

Será responsável por:

-   autenticação;
-   autorização;
-   validação;
-   regras da API;
-   conversão de lead em cliente;
-   transações;
-   comunicação segura com o banco.

### Frontend

Será responsável por:

-   tela de login;
-   Kanban de leads;
-   gestão de clientes;
-   Kanban de projetos;
-   checklists;
-   metas;
-   indicadores;
-   tema claro/escuro;
-   gerenciamento de usuários pelo administrador.

O frontend **não acessará diretamente o PostgreSQL**.

------------------------------------------------------------------------

## 19. Estrutura planejada do repositório

``` text
artx-crm/
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

### Organização sugerida

-   `database/schema.sql`: criação das tabelas e constraints;
-   `database/triggers.sql`: funções e triggers;
-   `database/seed.sql`: dados fictícios opcionais para desenvolvimento;
-   `docs/database.md`: este documento;
-   `docs/backend.md`: documentação futura da API;
-   `docs/architecture.md`: arquitetura geral;
-   `.env`: credenciais locais --- **não versionar**;
-   `.env.example`: nomes das variáveis necessárias, sem segredos.

------------------------------------------------------------------------

## 20. Estado atual

### Banco de dados --- MVP inicial

-   [x] Leads
-   [x] Histórico de leads
-   [x] Clientes
-   [x] Projetos
-   [x] Checklist de projetos
-   [x] Metas mensais
-   [x] Usuários
-   [x] Chaves primárias
-   [x] Chaves estrangeiras
-   [x] Restrições `CHECK`
-   [x] Restrições `UNIQUE`
-   [x] Histórico automático das movimentações de leads
-   [x] Atualização automática de timestamps
-   [x] Consulta de prospecções realizadas
-   [x] Consulta de reuniões realizadas
-   [x] Consulta de novos faturamentos
-   [x] Cálculo de percentual de atingimento das metas

### Próxima etapa

``` text
Python
  ↓
FastAPI
  ↓
SQLAlchemy
  ↓
PostgreSQL / CRM_artX
  ↓
Endpoints da API
  ↓
Autenticação
```

------------------------------------------------------------------------

## 21. Próximas melhorias previstas

A modelagem deverá evoluir junto com o desenvolvimento da aplicação.
Entre os próximos pontos estão:

-   implementação da autenticação no backend;
-   criação segura do primeiro administrador;
-   endpoints CRUD;
-   conversão transacional de lead em cliente;
-   encerramento de clientes;
-   consultas por mês parametrizadas;
-   integração com o frontend;
-   testes automatizados;
-   migrations;
-   índices conforme o volume e os padrões reais de consulta;
-   documentação da API;
-   deploy.

------------------------------------------------------------------------

## 22. Tecnologias

-   **PostgreSQL** --- banco de dados relacional;
-   **pgAdmin 4** --- administração do banco durante o desenvolvimento;
-   **Python** --- linguagem planejada para o backend;
-   **FastAPI** --- framework planejado para a API;
-   **SQLAlchemy** --- ORM planejado;
-   **React / Next.js** --- stack planejada para o frontend.

------------------------------------------------------------------------

## Observação

Este documento representa a modelagem do banco de dados na fase inicial
do **CRM ART X** e será atualizado conforme novas regras de negócio e
funcionalidades forem implementadas.
