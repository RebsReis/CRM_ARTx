import datetime

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from sqlalchemy import func, extract
from datetime import date,datetime
from sqlalchemy.exc import IntegrityError
from database import get_db

from typing import Optional
from pydantic import BaseModel, Field
from database import SessionLocal
from models import Lead, HistoricoLead,Cliente,ClienteValorMensal,Projeto, ChecklistItem, Meta,Reuniao
from fastapi import FastAPI, HTTPException, Query

from fastapi import HTTPException, status,Depends
from sqlalchemy.orm import Session
from schemas import ChecklistUpdate, LeadCreate, LeadFaseUpdate, ClienteCreate,ProjetoCreate,ProjetoStatusUpdate, ChecklistItemCreate, ChecklistStatusUpdate,ProjetoUpdate, MetaCreate, ReuniaoCreate, ClienteReajusteCreate
from sqlalchemy import select, text

import logging
import os
from auth import ORIGINS, proteger_crm, router as auth_router
from auth_public import router as cadastro_router
from financeiro import registrar_valor_inicial, registrar_reajuste, faturamento_recorrente_atual, faturamento_competencia, novos_faturamentos_competencia
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)

# A documentacao interativa expoe todas as rotas sem login; fica desligada salvo pedido explicito.
DOCS_ATIVOS = os.getenv("API_DOCS_ENABLED", "false").lower() == "true"

app = FastAPI(
    title="CRM ART X API",
    dependencies=[Depends(proteger_crm)],
    docs_url="/docs" if DOCS_ATIVOS else None,
    redoc_url="/redoc" if DOCS_ATIVOS else None,
    openapi_url="/openapi.json" if DOCS_ATIVOS else None,
)
app.include_router(auth_router)
app.include_router(cadastro_router)


@app.exception_handler(RequestValidationError)
async def erro_validacao_seguro(request, exc):
    # O erro padrao do Pydantic inclui o input, que pode conter uma senha.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(item["loc"]), "msg": item["msg"], "type": item["type"]}
        for item in exc.errors()
    ]})
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def inicio():
    return {
        "mensagem": "API do CRM ART X funcionando!"
    }


@app.get("/leads")
def listar_leads():


# O with garante que a sessão seja fechada quando terminarmos a operação, inclusive se ocorrer algum erro
    with SessionLocal() as db: #Agora estamos utilizando essa estrutura para trabalhar com o banco.

        consulta = select(Lead).where(Lead.arquivado_em.is_(None)).order_by(Lead.id)

        resultado = db.execute(consulta) #Aqui o SQLAlchemy envia a consulta ao PostgreSQL.

        leads = resultado.scalars().all() #O scalars() extrai os objetos Lead retornados pela consulta, e o all() reúne todos em uma lista.

        return leads

@app.post("/leads", status_code=status.HTTP_201_CREATED)
def criar_lead(dados: LeadCreate): #O FastAPI utiliza nosso schema Pydantic para validar automaticamente as informações recebidas.

    with SessionLocal() as db:
        novo_lead = Lead(
            nome_empresa=dados.nome_empresa,
            nicho=dados.nicho,
            telefone=dados.telefone,
            email=dados.email,
            fase=dados.fase,
            observacao=dados.observacao
        )

        db.add(novo_lead)#Adiciona o objeto à sessão do SQLAlchemy, preparando-o para ser inserido no banco.


        try:
            db.commit()#Confirma a transação e grava o novo lead no PostgreSQL.
            db.refresh(novo_lead)#Atualiza o objeto com os dados gerados pelo banco, como id e timestamps.

        except Exception:
            db.rollback()

            logger.exception("Erro ao cadastrar lead")

            raise HTTPException(
                status_code=500,
                detail="Não foi possível cadastrar o lead."
    )

        return novo_lead
def primeira_prospeccao_historica(db: Session, lead_id: int):
    return db.scalar(
        select(func.min(HistoricoLead.movimentado_em)).where(
            HistoricoLead.lead_id == lead_id,
            HistoricoLead.fase_anterior == "PROSPECTAR",
            HistoricoLead.fase_nova.in_([
                "FOLLOW_UP", "REUNIAO_MARCADA", "REMARKETING_FUTURO"
            ]),
        )
    )


@app.patch("/leads/{lead_id}/fase")
def atualizar_fase_lead(
    lead_id: int,
    dados: LeadFaseUpdate,
    db: Session = Depends(get_db),
):
    # Serializa transicoes do mesmo lead e grava fase/data em um unico commit.
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
    if lead is None or lead.arquivado_em is not None:
        raise HTTPException(status_code=404, detail="Lead nao encontrado.")
    if lead.fase == dados.fase:
        return {"mensagem": "O lead ja esta nessa fase.", "lead_id": lead.id, "fase": lead.fase}
    fase_anterior = lead.fase
    try:
        if lead.prospectado_em is None:
            primeira_data = primeira_prospeccao_historica(db, lead_id)
            if primeira_data is not None:
                lead.prospectado_em = primeira_data
            elif fase_anterior == "PROSPECTAR":
                # Mesmo relogio/fuso usado pelo historico no PostgreSQL.
                lead.prospectado_em = db.scalar(select(func.localtimestamp()))
        lead.fase = dados.fase
        if dados.fase == "REUNIAO_MARCADA":
            agendado_em = db.scalar(select(func.localtimestamp()))
            db.add(Reuniao(
                lead_id=lead.id,
                status="AGENDADA",
                criado_em=agendado_em,
                data_reuniao=agendado_em,
            ))
        db.commit()
        db.refresh(lead)
    except Exception:
        db.rollback()
        logger.exception("Erro ao atualizar fase do lead")
        raise HTTPException(status_code=500, detail="Nao foi possivel atualizar a fase.")
    return {
        "mensagem": "Fase atualizada com sucesso!", "lead_id": lead.id,
        "nome_empresa": lead.nome_empresa, "fase_anterior": fase_anterior,
        "fase_atual": lead.fase,
    }

@app.get("/leads/{lead_id}/historico")
def consultar_historico_lead(lead_id: int):

    with SessionLocal() as db:

        lead = db.get(Lead, lead_id) #lead existe no PostgreSQL. Caso contrário, retornamos o erro 404.

        if lead is None:
            raise HTTPException(
                status_code=404,
                detail="Lead não encontrado."
            )

        consulta = (
            select(HistoricoLead)
            .where(HistoricoLead.lead_id == lead_id)#Filtrar o histórico
            .order_by( #Ordenar as movimentações
                HistoricoLead.movimentado_em.desc(),
                HistoricoLead.id.desc()
            )
        )

        resultado = db.execute(consulta)

        historico = resultado.scalars().all()

        return historico

@app.get("/metas/prospeccoes")
def consultar_prospeccoes_realizadas(
    ano: int = Query(ge=2000, le=2100), #define os parâmetros recebidos pela URL e suas validações.ge=1 significa maior ou igual a 1, enquanto le=12 significa menor ou igual a 12.
    mes: int = Query(ge=1, le=12)
):
    sql = text("""
        WITH primeira_prospeccao AS (
            SELECT
                lead_id,
                MIN(movimentado_em) AS data_prospeccao
            FROM historico_leads
            WHERE fase_anterior = 'PROSPECTAR'
              AND fase_nova IN (
                  'FOLLOW_UP',
                  'REUNIAO_MARCADA',
                  'REMARKETING_FUTURO'
              )
            GROUP BY lead_id
        )
        SELECT COUNT(*)
        FROM primeira_prospeccao
        WHERE EXTRACT(YEAR FROM data_prospeccao) = :ano
          AND EXTRACT(MONTH FROM data_prospeccao) = :mes
    """)

    with SessionLocal() as db:
        resultado = db.execute(
            sql,
            {"ano": ano, "mes": mes}
        ).scalar_one()

        return {
            "ano": ano,
            "mes": mes,
            "prospeccoes_realizadas": resultado
        }

@app.get("/metas/prospeccoes/resumo")
def resumo_meta_prospeccoes(
    ano: int = Query(ge=2000, le=2100),
    mes: int = Query(ge=1, le=12)
):
    sql = text("""
        WITH primeira_prospeccao AS (
            SELECT
                lead_id,
                MIN(movimentado_em) AS data_prospeccao
            FROM historico_leads
            WHERE fase_anterior = 'PROSPECTAR'
              AND fase_nova IN (
                  'FOLLOW_UP',
                  'REUNIAO_MARCADA',
                  'REMARKETING_FUTURO'
              )
            GROUP BY lead_id
        )
        SELECT
            m.meta_prospeccoes,
            (
                SELECT COUNT(*)
                FROM primeira_prospeccao p
                WHERE EXTRACT(YEAR FROM p.data_prospeccao) = :ano
                  AND EXTRACT(MONTH FROM p.data_prospeccao) = :mes
            ) AS realizadas
        FROM metas m
        WHERE m.ano = :ano
          AND m.mes = :mes
    """)

    with SessionLocal() as db:
        resultado = db.execute(
            sql,
            {"ano": ano, "mes": mes}
        ).mappings().first()

        if resultado is None:
            raise HTTPException(
                status_code=404,
                detail="Nenhuma meta cadastrada para este mês."
            )

        meta = resultado["meta_prospeccoes"]
        realizadas = resultado["realizadas"]

        percentual = (
            round(realizadas / meta * 100, 2)
            if meta > 0 else 0
        )

        return {
            "ano": ano,
            "mes": mes,
            "meta_prospeccoes": meta,
            "prospeccoes_realizadas": realizadas,
            "percentual_atingido": percentual
        }

@app.get("/metas/reunioes/resumo")
def resumo_meta_reunioes(ano: int, mes: int):
    if not 1 <= mes <= 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )
    if not 2000 <= ano <= 2100:
        raise HTTPException(
            status_code=400,
            detail="O ano deve estar entre 2000 e 2100."
        )

    with SessionLocal() as db:
        # Busca a meta cadastrada para o mês
        meta = db.execute(
            text("""
                SELECT meta_reunioes
                FROM metas
                WHERE ano = :ano AND mes = :mes
            """),
            {"ano": ano, "mes": mes}
        ).scalar_one_or_none()

        # Conta as reuniões registradas no histórico
        realizadas = contar_reunioes_mensais(db, ano, mes)

    percentual = (
        round((realizadas / meta) * 100, 2)
        if meta is not None and meta > 0
        else None
    )

    return {
        "ano": ano,
        "mes": mes,
        "meta_reunioes": meta,
        "reunioes_marcadas": realizadas,
        "percentual_atingido": percentual
    }


@app.get("/metas/faturamento")
def consultar_novos_faturamentos(ano: int, mes: int):
    if not 1 <= mes <= 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )
    if not 2000 <= ano <= 2100:
        raise HTTPException(
            status_code=400,
            detail="O ano deve estar entre 2000 e 2100."
        )

    with SessionLocal() as db:
        resultado = novos_faturamentos_competencia(db, ano, mes)

    return {
        "ano": ano,
        "mes": mes,
        "novos_faturamentos": float(resultado)
    }


@app.get("/metas/faturamento/resumo")
def resumo_meta_faturamento(ano: int, mes: int):
    if not 1 <= mes <= 12:
        raise HTTPException(
            status_code=400,
            detail="O mês deve estar entre 1 e 12."
        )
    if not 2000 <= ano <= 2100:
        raise HTTPException(
            status_code=400,
            detail="O ano deve estar entre 2000 e 2100."
        )

    with SessionLocal() as db:
        # Busca a meta mensal no PostgreSQL
        meta = db.execute(
            text("""
                SELECT meta_faturamento
                FROM metas
                WHERE ano = :ano AND mes = :mes
            """),
            {"ano": ano, "mes": mes}
        ).scalar_one_or_none()

        # Soma somente os novos contratos do mês
        realizado = novos_faturamentos_competencia(db, ano, mes)

    percentual = (
        round((realizado / meta) * 100, 2)
        if meta is not None and meta > 0
        else None
    )

    return {
        "ano": ano,
        "mes": mes,
        "meta_faturamento": float(meta) if meta is not None else None,
        "novos_faturamentos": float(realizado),
        "percentual_atingido": float(percentual) if percentual is not None else None
    }


@app.get("/clientes")
def listar_clientes():
    with SessionLocal() as db:
        clientes = db.query(Cliente).order_by(Cliente.id).all() 

        return [
            {
                "id": cliente.id,
                "nome_empresa": cliente.nome_empresa,
                "nicho": cliente.nicho,
                "telefone": cliente.telefone,
                "email": cliente.email,
                "valor_mensal": cliente.valor_mensal,
                "data_inicio": cliente.data_inicio,
                "data_encerramento": cliente.data_encerramento,
                "status": cliente.status
            }
            for cliente in clientes
        ]

@app.post("/clientes", status_code=status.HTTP_201_CREATED)
def criar_cliente(dados: ClienteCreate):

    with SessionLocal() as db:

        novo_cliente = Cliente(
            nome_empresa=dados.nome_empresa,
            nicho=dados.nicho,
            telefone=dados.telefone,
            email=dados.email,
            valor_mensal=dados.valor_mensal,
            data_inicio=dados.data_inicio or date.today(),
            status="ATIVO"
        )

        try:
            db.add(novo_cliente)
            db.flush()
            registrar_valor_inicial(db, novo_cliente, origem="CADASTRO", inicio=novo_cliente.data_inicio)
            db.commit()
            db.refresh(novo_cliente)

        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=400,
                detail="Dados inválidos para o cadastro do cliente."
            )

        return {
            "mensagem": "Cliente cadastrado com sucesso!",
            "id": novo_cliente.id,
            "nome_empresa": novo_cliente.nome_empresa,
            "valor_mensal": novo_cliente.valor_mensal,
            "status": novo_cliente.status
        }
@app.patch("/clientes/{cliente_id}/encerrar")
def encerrar_cliente(cliente_id: int):

    with SessionLocal() as db:

        cliente = db.get(Cliente, cliente_id)

        if cliente is None:
            raise HTTPException(
                status_code=404,
                detail="Cliente não encontrado."
            )

        if cliente.status == "INATIVO":
            return {
                "mensagem": "Este contrato já está encerrado.",
                "cliente_id": cliente.id
            }

        cliente.status = "INATIVO"
        cliente.data_encerramento = date.today()

        db.commit()
        db.refresh(cliente)

        return {
            "mensagem": "Contrato encerrado com sucesso!",
            "cliente_id": cliente.id,
            "nome_empresa": cliente.nome_empresa,
            "status": cliente.status,
            "data_encerramento": cliente.data_encerramento
        }
@app.get("/clientes/faturamento/recorrente")
def faturamento_recorrente():

    with SessionLocal() as db:

        faturamento_total = faturamento_recorrente_atual(db)
        clientes_ativos = db.query(Cliente).filter(Cliente.status == "ATIVO").count()

        return {
            "faturamento_mensal": float(faturamento_total),
            "clientes_ativos": clientes_ativos
        }
from datetime import date
from fastapi import Query

@app.get("/clientes/faturamento/mensal")
def faturamento_mensal(
    ano: int = Query(..., ge=2000, le=2100),
    mes: int = Query(..., ge=1, le=12)
):
    if mes == 12:
        proximo_mes = date(ano + 1, 1, 1)
    else:
        proximo_mes = date(ano, mes + 1, 1)

    inicio_mes = date(ano, mes, 1)

    with SessionLocal() as db:
        total = faturamento_competencia(db, ano, mes)
        clientes_no_periodo = db.query(Cliente).filter(
            Cliente.data_inicio < proximo_mes,
            ((Cliente.data_encerramento == None) | (Cliente.data_encerramento >= inicio_mes))
        ).count()

        return {
            "ano": ano,
            "mes": mes,
            "faturamento_recorrente": float(total),
            "clientes_no_periodo": clientes_no_periodo
        }


@app.get("/projetos")
def listar_projetos():

    with SessionLocal() as db:

        projetos = db.query(Projeto).all()

        resultado = []

        for projeto in projetos:

            cliente = db.get(Cliente, projeto.cliente_id)

            resultado.append({
                "id": projeto.id,
                "cliente_id": projeto.cliente_id,
                "nome_cliente": cliente.nome_empresa if cliente else None,
                "nome_projeto": projeto.nome_projeto,
                "prazo": projeto.prazo,
                "prioridade": projeto.prioridade,
                "status": projeto.status,
                "observacao": projeto.observacao
            })

        return resultado


@app.post("/projetos", status_code=201)
def criar_projeto(dados: ProjetoCreate):

    with SessionLocal() as db:

        # 1. Verificar se o cliente existe
        cliente = db.get(Cliente, dados.cliente_id)

        if cliente is None:
            raise HTTPException(
                status_code=404,
                detail="Cliente não encontrado."
            )

        # 2. Criar o projeto
        novo_projeto = Projeto(
            cliente_id=dados.cliente_id,
            nome_projeto=dados.nome_projeto,
            prazo=dados.prazo,
            prioridade=dados.prioridade,
            status=dados.status,
            observacao=dados.observacao
        )

        # 3. Salvar no PostgreSQL
        db.add(novo_projeto)
        db.commit()
        db.refresh(novo_projeto)

        # 4. Retornar o projeto cadastrado
        return {
            "mensagem": "Projeto cadastrado com sucesso!",
            "id": novo_projeto.id,
            "cliente_id": novo_projeto.cliente_id,
            "nome_cliente": cliente.nome_empresa,
            "nome_projeto": novo_projeto.nome_projeto,
            "prazo": novo_projeto.prazo,
            "prioridade": novo_projeto.prioridade,
            "status": novo_projeto.status
        }



@app.patch("/projetos/{projeto_id}/status")
def atualizar_status_projeto(
    projeto_id: int,
    dados: ProjetoStatusUpdate,
    db: Session = Depends(get_db)
):
    projeto = db.query(Projeto).filter(
        Projeto.id == projeto_id
    ).first()

    if not projeto:
        raise HTTPException(
            status_code=404,
            detail="Projeto não encontrado"
        )

    projeto.status = dados.status
    projeto.atualizado_em = datetime.now()

    db.commit()
    db.refresh(projeto)

    return {
        "mensagem": "Status atualizado com sucesso!",
        "projeto_id": projeto.id,
        "nome_projeto": projeto.nome_projeto,
        "status": projeto.status

    
}


@app.post("/projetos/{projeto_id}/checklist", status_code=201)
def adicionar_tarefa(
    projeto_id: int,
    dados: ChecklistItemCreate,
    db: Session = Depends(get_db)
):
    projeto = db.query(Projeto).filter(
        Projeto.id == projeto_id
    ).first()

    if not projeto:
        raise HTTPException(
            status_code=404,
            detail="Projeto não encontrado"
        )

    nova_tarefa = ChecklistItem(
        projeto_id=projeto_id,
        descricao=dados.descricao,
        ordem=dados.ordem,
        concluido=False
    )

    db.add(nova_tarefa)
    db.commit()
    db.refresh(nova_tarefa)

    return {
        "mensagem": "Tarefa cadastrada com sucesso!",
        "id": nova_tarefa.id,
        "projeto_id": nova_tarefa.projeto_id,
        "descricao": nova_tarefa.descricao,
        "concluido": nova_tarefa.concluido,
        "ordem": nova_tarefa.ordem
    }
@app.patch("/checklist/{item_id}/concluir")
def atualizar_status_checklist(
    item_id: int,
    dados: ChecklistStatusUpdate,
    db: Session = Depends(get_db)
):
    tarefa = db.query(ChecklistItem).filter(
        ChecklistItem.id == item_id
    ).first()

    if not tarefa:
        raise HTTPException(
            status_code=404,
            detail="Tarefa não encontrada"
        )

    tarefa.concluido = dados.concluido

    if dados.concluido:
        tarefa.concluido_em = datetime.now()
    else:
        tarefa.concluido_em = None

    db.commit()
    db.refresh(tarefa)

    return {
        "message": "Status da tarefa atualizado com sucesso!",
        "id": tarefa.id,
        "descricao": tarefa.descricao,
        "concluido": tarefa.concluido,
        "concluido_em": tarefa.concluido_em
    }

@app.get("/projetos/{projeto_id}/checklist")
def listar_checklist_projeto(
    projeto_id: int,
    db: Session = Depends(get_db)
):
    projeto = db.query(Projeto).filter(
        Projeto.id == projeto_id
    ).first()

    if not projeto:
        raise HTTPException(
            status_code=404,
            detail="Projeto não encontrado"
        )

    tarefas = db.query(ChecklistItem).filter(
        ChecklistItem.projeto_id == projeto_id
    ).order_by(
        ChecklistItem.ordem,
        ChecklistItem.id
    ).all()

    return [
        {
            "id": tarefa.id,
            "projeto_id": tarefa.projeto_id,
            "descricao": tarefa.descricao,
            "concluido": tarefa.concluido,
            "ordem": tarefa.ordem,
            "criado_em": tarefa.criado_em,
            "concluido_em": tarefa.concluido_em
        }
        for tarefa in tarefas
    ]


@app.delete("/checklist/{tarefa_id}")
def excluir_tarefa(
    tarefa_id: int,
    db: Session = Depends(get_db)
):
    tarefa = db.query(ChecklistItem).filter(
        ChecklistItem.id == tarefa_id
    ).first()

    if not tarefa:
        raise HTTPException(
            status_code=404,
            detail="Tarefa não encontrada"
        )

    db.delete(tarefa)
    db.commit()

    return {
        "message": "Tarefa excluída com sucesso!",
        "tarefa_id": tarefa_id
    }

@app.patch("/checklist/{tarefa_id}")
def editar_tarefa(
    tarefa_id: int,
    dados: ChecklistUpdate,
    db: Session = Depends(get_db)
):
    tarefa = db.query(ChecklistItem).filter(
        ChecklistItem.id == tarefa_id
    ).first()

    if not tarefa:
        raise HTTPException(
            status_code=404,
            detail="Tarefa não encontrada"
        )

    if dados.descricao is not None:
        tarefa.descricao = dados.descricao

    if dados.ordem is not None:
        tarefa.ordem = dados.ordem

    db.commit()
    db.refresh(tarefa)

    return {
        "message": "Tarefa atualizada com sucesso!",
        "id": tarefa.id,
        "projeto_id": tarefa.projeto_id,
        "descricao": tarefa.descricao,
        "ordem": tarefa.ordem,
        "concluido": tarefa.concluido
    }


@app.patch("/projetos/{projeto_id}")
def editar_projeto(
    projeto_id: int,
    dados: ProjetoUpdate,
    db: Session = Depends(get_db)
):
    projeto = db.query(Projeto).filter(
        Projeto.id == projeto_id
    ).first()

    if not projeto:
        raise HTTPException(
            status_code=404,
            detail="Projeto não encontrado"
        )

    if dados.nome_projeto is not None:
        projeto.nome_projeto = dados.nome_projeto

    if dados.prazo is not None:
        projeto.prazo = dados.prazo

    if dados.prioridade is not None:
        projeto.prioridade = dados.prioridade

    if dados.observacao is not None:
        projeto.observacao = dados.observacao

    projeto.atualizado_em = datetime.now()

    db.commit()
    db.refresh(projeto)

    return {
        "message": "Projeto atualizado com sucesso!",
        "id": projeto.id,
        "nome_projeto": projeto.nome_projeto,
        "prazo": projeto.prazo,
        "prioridade": projeto.prioridade,
        "status": projeto.status,
        "observacao": projeto.observacao
    }


@app.delete("/projetos/{projeto_id}")
def excluir_projeto(
    projeto_id: int,
    db: Session = Depends(get_db)
):
    projeto = db.query(Projeto).filter(
        Projeto.id == projeto_id
    ).first()

    if not projeto:
        raise HTTPException(
            status_code=404,
            detail="Projeto não encontrado"
        )

    nome_projeto = projeto.nome_projeto

    db.delete(projeto)
    db.commit()

    return {
        "message": "Projeto excluído com sucesso!",
        "projeto_id": projeto_id,
        "nome_projeto": nome_projeto
    }

from sqlalchemy.exc import IntegrityError

@app.post("/metas", status_code=201)
def criar_meta(
    dados: MetaCreate,
    db: Session = Depends(get_db)
):
    meta_existente = db.query(Meta).filter(
        Meta.ano == dados.ano,
        Meta.mes == dados.mes
    ).first()

    if meta_existente:
        raise HTTPException(
            status_code=409,
            detail="Já existe uma meta cadastrada para este mês."
        )

    nova_meta = Meta(
        ano=dados.ano,
        mes=dados.mes,
        meta_prospeccoes=dados.meta_prospeccoes,
        meta_reunioes=dados.meta_reunioes,
        meta_faturamento=dados.meta_faturamento
    )

    db.add(nova_meta)

    try:
        db.commit()
        db.refresh(nova_meta)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Não foi possível cadastrar: meta mensal já existente."
        )

    return {
        "mensagem": "Meta cadastrada com sucesso!",
        "id": nova_meta.id,
        "ano": nova_meta.ano,
        "mes": nova_meta.mes,
        "meta_prospeccoes": nova_meta.meta_prospeccoes,
        "meta_reunioes": nova_meta.meta_reunioes,
        "meta_faturamento": float(nova_meta.meta_faturamento)
    }

@app.put("/metas/{meta_id}")
def atualizar_meta(
    meta_id: int,
    dados: MetaCreate,
    db: Session = Depends(get_db)
):
    meta = db.query(Meta).filter(
        Meta.id == meta_id
    ).first()

    if not meta:
        raise HTTPException(
            status_code=404,
            detail="Meta não encontrada"
        )

    meta.ano = dados.ano
    meta.mes = dados.mes
    meta.meta_prospeccoes = dados.meta_prospeccoes
    meta.meta_reunioes = dados.meta_reunioes
    meta.meta_faturamento = dados.meta_faturamento
    meta.atualizado_em = datetime.now()

    try:
        db.commit()
        db.refresh(meta)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe uma meta cadastrada para este período."
        )

    return {
        "mensagem": "Meta atualizada com sucesso!",
        "id": meta.id,
        "ano": meta.ano,
        "mes": meta.mes,
        "meta_prospeccoes": meta.meta_prospeccoes,
        "meta_reunioes": meta.meta_reunioes,
        "meta_faturamento": float(meta.meta_faturamento)
    }
@app.get("/metas")
def consultar_meta(
    ano: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    meta = db.query(Meta).filter(
        Meta.ano == ano,
        Meta.mes == mes
    ).first()

    if not meta:
        raise HTTPException(
            status_code=404,
            detail="Nenhuma meta cadastrada para este período."
        )

    return {
        "id": meta.id,
        "ano": meta.ano,
        "mes": meta.mes,
        "meta_prospeccoes": meta.meta_prospeccoes,
        "meta_reunioes": meta.meta_reunioes,
        "meta_faturamento": float(meta.meta_faturamento)
    }

@app.patch("/leads/{lead_id}/prospectar")
def registrar_prospeccao(
    lead_id: int,
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id
    ).with_for_update().first()

    if not lead or lead.arquivado_em is not None:
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado."
        )

    if lead.prospectado_em is not None:
        db.rollback()
        return {
            "mensagem": "Este lead já foi prospectado anteriormente.",
            "lead_id": lead.id,
            "prospectado_em": lead.prospectado_em,
            "contabilizado_agora": False
        }

    primeira_data = primeira_prospeccao_historica(db, lead_id)
    if primeira_data is None:
        raise HTTPException(status_code=409, detail="A prospeccao so pode ser registrada apos sair de PROSPECTAR.")
    lead.prospectado_em = primeira_data

    db.commit()
    db.refresh(lead)

    return {
        "mensagem": "Prospecção registrada com sucesso!",
        "lead_id": lead.id,
        "prospectado_em": lead.prospectado_em,
        "contabilizado_agora": True
    }

from sqlalchemy import func

def contar_leads_no_funil(db: Session, fases: list[str]) -> int:
    return db.scalar(select(func.count(Lead.id)).where(
        Lead.arquivado_em.is_(None), Lead.fase.in_(fases),
    )) or 0


def contar_prospeccoes_mensais(db: Session, ano: int, mes: int) -> int:
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return db.scalar(select(func.count(Lead.id)).where(
        Lead.prospectado_em >= inicio,
        Lead.prospectado_em < fim,
    )) or 0


@app.get("/leads/prospeccoes/mensal")
def consultar_prospeccoes_mensais(
    ano: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    total = contar_prospeccoes_mensais(db, ano, mes)

    return {
        "ano": ano,
        "mes": mes,
        "prospeccoes_realizadas": total or 0
    }

@app.get("/metas/progresso/prospeccoes")
def progresso_meta_prospeccoes(
    ano: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    meta = db.execute(
        text("""
            SELECT meta_prospeccoes
            FROM metas
            WHERE ano = :ano AND mes = :mes
        """),
        {"ano": ano, "mes": mes}
    ).scalar_one_or_none()

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Meta não cadastrada para este mês"
        )

    realizadas = contar_prospeccoes_mensais(db, ano, mes)

    percentual = (
        round(realizadas / meta * 100, 2)
        if meta > 0 else 0
    )

    return {
        "ano": ano,
        "mes": mes,
        "meta_prospeccoes": meta,
        "prospeccoes_realizadas": realizadas,
        "faltam": max(meta - realizadas, 0),
        "percentual_atingido": percentual
    }

@app.post("/reunioes", status_code=201)
def cadastrar_reuniao(
    dados: ReuniaoCreate,
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(
        Lead.id == dados.lead_id
    ).with_for_update().first()

    if not lead or lead.arquivado_em is not None:
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado"
        )

    nova_reuniao = Reuniao(
        lead_id=dados.lead_id,
        data_reuniao=dados.data_reuniao,
        status="AGENDADA",
        observacao=dados.observacao,
        criado_em=db.scalar(select(func.localtimestamp()))
    )

    db.add(nova_reuniao)
    db.commit()
    db.refresh(nova_reuniao)

    return {
        "mensagem": "Reunião agendada com sucesso!",
        "id": nova_reuniao.id,
        "lead_id": nova_reuniao.lead_id,
        "data_reuniao": nova_reuniao.data_reuniao,
        "status": nova_reuniao.status,
        "observacao": nova_reuniao.observacao
    }


def contar_reunioes_mensais(db: Session, ano: int, mes: int) -> int:
    inicio = date(ano, mes, 1)
    fim = date(ano + 1, 1, 1) if mes == 12 else date(ano, mes + 1, 1)
    return db.scalar(select(func.count(Reuniao.id)).where(
        Reuniao.criado_em >= inicio,
        Reuniao.criado_em < fim,
        Reuniao.status.in_(["AGENDADA", "REALIZADA"]),
    )) or 0


@app.get("/reunioes/indicadores/mensal")
def consultar_reunioes_mensais(
    ano: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    total = contar_reunioes_mensais(db, ano, mes)

    return {
        "ano": ano,
        "mes": mes,
        "reunioes_agendadas": total
    }


@app.get("/metas/progresso/reunioes")
def progresso_meta_reunioes(
    ano: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    meta = db.execute(
        text("""
            SELECT meta_reunioes
            FROM metas
            WHERE ano = :ano AND mes = :mes
        """),
        {"ano": ano, "mes": mes}
    ).scalar_one_or_none()

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Meta não cadastrada para este mês"
        )

    realizadas = contar_reunioes_mensais(db, ano, mes)

    percentual = (
        round(realizadas / meta * 100, 2)
        if meta > 0 else 0
    )

    return {
        "ano": ano,
        "mes": mes,
        "meta_reunioes": meta,
        "reunioes_realizadas": realizadas,
        "faltam": max(meta - realizadas, 0),
        "percentual_atingido": percentual
    }

@app.get("/metas/progresso/faturamento")
def progresso_meta_faturamento(
    ano: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    meta = db.execute(
        text("""
            SELECT meta_faturamento
            FROM metas
            WHERE ano = :ano AND mes = :mes
        """),
        {"ano": ano, "mes": mes}
    ).scalar_one_or_none()

    if meta is None:
        raise HTTPException(
            status_code=404,
            detail="Meta não cadastrada para este mês"
        )

    faturamento = faturamento_competencia(db, ano, mes)

    percentual = (
        round(float(faturamento / meta) * 100, 2)
        if meta > 0 else 0
    )

    return {
        "ano": ano,
        "mes": mes,
        "meta_faturamento": float(meta),
        "faturamento_recorrente": float(faturamento),
        "faltam": float(max(meta - faturamento, 0)),
        "percentual_atingido": percentual
    }


@app.get("/metas/dashboard")
def dashboard_metas(
    ano: int = Query(..., ge=2020, le=2100),
    mes: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db)
):
    prospeccoes = progresso_meta_prospeccoes(
        ano=ano, mes=mes, db=db
    )

    reunioes = progresso_meta_reunioes(
        ano=ano, mes=mes, db=db
    )

    faturamento = progresso_meta_faturamento(
        ano=ano, mes=mes, db=db
    )

    return {
        "ano": ano,
        "mes": mes,
        "prospeccoes": prospeccoes,
        "reunioes": reunioes,
        "faturamento": faturamento
    }



class FechamentoContrato(BaseModel):
    valor_mensal: float = Field(gt=0)


@app.post("/leads/{lead_id}/fechar")
def fechar_contrato(
    lead_id: int,
    dados: FechamentoContrato,
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(
        Lead.id == lead_id
    ).with_for_update().first()

    if lead is None or lead.arquivado_em is not None:
        raise HTTPException(
            status_code=404,
            detail="Lead não encontrado."
        )

    if lead.fase != "REUNIAO_MARCADA":
        raise HTTPException(
            status_code=400,
            detail="O lead precisa estar na etapa Reunião Marcada."
        )

    novo_cliente = Cliente(
        lead_id=lead.id,
        nome_empresa=lead.nome_empresa,
        nicho=lead.nicho,
        telefone=lead.telefone,
        email=lead.email,
        valor_mensal=dados.valor_mensal,
        data_inicio=date.today(),
        status="ATIVO"
    )

    try:
        db.add(novo_cliente)
        db.flush()
        registrar_valor_inicial(db, novo_cliente, origem="CADASTRO", inicio=novo_cliente.data_inicio)

        lead.arquivado_em = db.scalar(select(func.localtimestamp()))
        db.commit()

        return {
            "mensagem": "Contrato fechado com sucesso!",
            "cliente_id": novo_cliente.id,
            "nome_empresa": novo_cliente.nome_empresa,
            "valor_mensal": float(novo_cliente.valor_mensal)
        }

    except Exception:
        db.rollback()
        logger.exception("Erro ao fechar contrato")

        raise HTTPException(
            status_code=500,
            detail="Não foi possível fechar o contrato."
        )



class LeadUpdate(BaseModel):
    nome_empresa: str = Field(min_length=1, max_length=150)
    nicho: Optional[str] = Field(default=None, max_length=100)
    telefone: Optional[str] = Field(default=None, max_length=30)
    email: Optional[str] = Field(default=None, max_length=150)
    observacao: Optional[str] = None


@app.patch("/leads/{lead_id}")
def editar_lead(lead_id: int, dados: LeadUpdate, db: Session = Depends(get_db)):
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
    if lead is None or lead.arquivado_em is not None:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    nome = dados.nome_empresa.strip()
    if not nome:
        raise HTTPException(status_code=400, detail="Informe o nome da empresa.")
    for campo, valor in dados.model_dump().items():
        setattr(lead, campo, nome if campo == "nome_empresa" else valor)
    try:
        db.commit()
        db.refresh(lead)
    except Exception:
        db.rollback()
        logger.exception("Erro ao editar lead")
        raise HTTPException(status_code=500, detail="Não foi possível editar o lead.")
    return lead


@app.delete("/leads/{lead_id}", status_code=204)
def excluir_lead(lead_id: int, db: Session = Depends(get_db)):
    lead = db.scalar(select(Lead).where(Lead.id == lead_id).with_for_update())
    if lead is None or lead.arquivado_em is not None:
        raise HTTPException(status_code=404, detail="Lead não encontrado.")
    try:
        lead.arquivado_em = db.scalar(select(func.localtimestamp()))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Este lead possui registros vinculados e não pode ser excluído.")
    except Exception:
        db.rollback()
        logger.exception("Erro ao excluir lead")
        raise HTTPException(status_code=500, detail="Não foi possível excluir o lead.")


class ClienteUpdate(BaseModel):
    nome_empresa: Optional[str] = None
    nicho: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    valor_mensal: Optional[float] = Field(default=None, gt=0)


@app.patch("/clientes/{cliente_id}")
def editar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: Session = Depends(get_db)
):
    cliente = db.get(Cliente, cliente_id)

    if cliente is None:
        raise HTTPException(
            status_code=404,
            detail="Cliente não encontrado."
        )

    alteracoes = dados.model_dump(exclude_unset=True)

    novo_valor = alteracoes.pop("valor_mensal", None) if "valor_mensal" in alteracoes else None
    if novo_valor is not None:
        registrar_reajuste(db, cliente_id, novo_valor)

    if "nome_empresa" in alteracoes:
        nome = alteracoes["nome_empresa"]

        if not nome or not nome.strip():
            raise HTTPException(
                status_code=400,
                detail="O nome da empresa é obrigatório."
            )

        alteracoes["nome_empresa"] = nome.strip()

    for campo, valor in alteracoes.items():
        setattr(cliente, campo, valor)

    try:
        db.commit()
        db.refresh(cliente)

    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Não foi possível atualizar o cliente."
        )

    return {
        "mensagem": "Cliente atualizado com sucesso!",
        "id": cliente.id,
        "nome_empresa": cliente.nome_empresa,
        "nicho": cliente.nicho,
        "telefone": cliente.telefone,
        "email": cliente.email,
        "valor_mensal": float(cliente.valor_mensal),
        "status": cliente.status
    }


@app.post("/clientes/{cliente_id}/reajustes", status_code=201)
def criar_reajuste_cliente(cliente_id: int, dados: ClienteReajusteCreate, db: Session = Depends(get_db)):
    try:
        registro = registrar_reajuste(db, cliente_id, dados.valor_mensal, dados.vigencia_inicio)
        db.commit()
        db.refresh(registro)
        return {
            "id": registro.id,
            "cliente_id": registro.cliente_id,
            "valor_mensal": float(registro.valor_mensal),
            "vigencia_inicio": registro.vigencia_inicio,
            "vigencia_fim": registro.vigencia_fim,
            "origem": registro.origem,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Erro ao criar reajuste")
        raise HTTPException(status_code=500, detail="Não foi possível criar o reajuste.")


@app.get("/clientes/{cliente_id}/historico-valores")
def listar_historico_valores(cliente_id: int, db: Session = Depends(get_db)):
    if db.get(Cliente, cliente_id) is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    registros = db.scalars(select(ClienteValorMensal).where(
        ClienteValorMensal.cliente_id == cliente_id
    ).order_by(ClienteValorMensal.vigencia_inicio)).all()
    return [{
        "id": item.id,
        "cliente_id": item.cliente_id,
        "valor_mensal": float(item.valor_mensal),
        "vigencia_inicio": item.vigencia_inicio,
        "vigencia_fim": item.vigencia_fim,
        "origem": item.origem,
        "criado_em": item.criado_em,
    } for item in registros]
