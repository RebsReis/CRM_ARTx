"""Real PostgreSQL tests in a disposable schema; no production rows are changed."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy import event, func, select, text

import main
import test_prospeccoes as support
from models import Cliente, HistoricoLead, Lead, Meta, Reuniao
from schemas import LeadFaseUpdate, ReuniaoCreate


class ReunioesPostgresTest(unittest.TestCase):
    novo = support.ProspeccoesPostgresTest.novo
    mover = support.ProspeccoesPostgresTest.mover
    total = support.ProspeccoesPostgresTest.total
    data = support.ProspeccoesPostgresTest.data
    tearDownClass = classmethod(support.ProspeccoesPostgresTest.tearDownClass.__func__)

    @classmethod
    def setUpClass(cls):
        support.ProspeccoesPostgresTest.setUpClass.__func__(cls)
        with cls.test_engine.begin() as c:
            c.execute(text("ALTER TABLE historico_leads ADD CONSTRAINT fk_test_historico FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE"))
            sql = Path(__file__).with_name("migrations").joinpath("20261016_preservar_leads_historicos.sql").read_text()
            c.execute(text(sql))
            c.execute(text(sql))

    def contagem(self):
        with self.sessions() as db:
            now = db.scalar(select(func.localtimestamp()))
            meta = db.scalar(select(Meta).where(Meta.ano == now.year, Meta.mes == now.month))
            if meta is None:
                db.add(Meta(ano=now.year, mes=now.month, meta_prospeccoes=100, meta_reunioes=10, meta_faturamento=1000))
                db.commit()
            mensal = main.consultar_reunioes_mensais(now.year, now.month, db)["reunioes_agendadas"]
            dashboard = main.dashboard_metas(now.year, now.month, db)
            self.assertEqual(main.contar_leads_no_funil(db, ["REUNIAO_MARCADA"]), dashboard["reunioes"]["reunioes_realizadas"])
            return mensal, main.contar_prospeccoes_mensais(db, now.year, now.month)

    def test_metas_refletem_funil_atual_sem_apagar_historico(self):
        self.contagem()  # Garante as metas do mes no schema isolado.
        with self.sessions() as db:
            agora = db.scalar(select(func.localtimestamp()))
            base = main.dashboard_metas(agora.year, agora.month, db)
        p = base["prospeccoes"]["prospeccoes_realizadas"]
        r = base["reunioes"]["reunioes_realizadas"]
        lead_id = self.novo()
        for fase, prospeccoes, reunioes in [
            ("PROSPECTAR", p, r), ("FOLLOW_UP", p + 1, r),
            ("REUNIAO_MARCADA", p + 1, r + 1),
            ("REMARKETING_FUTURO", p + 1, r),
            ("PROSPECTAR", p, r), ("REUNIAO_MARCADA", p + 1, r + 1),
        ]:
            self.mover(lead_id, fase)
            with self.sessions() as db:
                painel = main.dashboard_metas(agora.year, agora.month, db)
                self.assertEqual(painel["prospeccoes"]["prospeccoes_realizadas"], prospeccoes)
                self.assertEqual(painel["reunioes"]["reunioes_realizadas"], reunioes)
        with self.sessions() as db:
            historico = db.scalar(select(func.count(Reuniao.id)).where(Reuniao.lead_id == lead_id))
            self.assertEqual(historico, 2)
            main.excluir_lead(lead_id, db)
        with self.sessions() as db:
            painel = main.dashboard_metas(agora.year, agora.month, db)
            self.assertEqual(painel["prospeccoes"]["prospeccoes_realizadas"], p)
            self.assertEqual(painel["reunioes"]["reunioes_realizadas"], r)
            self.assertEqual(db.scalar(select(func.count(Reuniao.id)).where(Reuniao.lead_id == lead_id)), historico)

    def test_entrada_repeticao_retorno_e_recarregamento(self):
        antes, _ = self.contagem()
        lead_id = self.novo()
        self.assertEqual(self.contagem()[0], antes)
        self.mover(lead_id, "REUNIAO_MARCADA")
        self.assertEqual(self.contagem()[0], antes + 1)
        self.mover(lead_id, "REUNIAO_MARCADA")
        self.assertEqual(self.contagem()[0], antes + 1)
        self.mover(lead_id, "FOLLOW_UP")
        self.mover(lead_id, "REUNIAO_MARCADA")
        self.assertEqual(self.contagem()[0], antes + 2)
        # Repeated reads/new sessions model browser reload: no new meeting.
        self.assertEqual(self.contagem()[0], antes + 2)
        with self.sessions() as db:
            reunioes = db.scalars(select(Reuniao).where(Reuniao.lead_id == lead_id)).all()
            self.assertEqual(len(reunioes), 2)
            for reuniao in reunioes:
                self.assertEqual(reuniao.criado_em, reuniao.data_reuniao)
                self.assertEqual(reuniao.status, "AGENDADA")

    def test_fechamento_preserva_indicadores_vinculos_e_historico(self):
        lead_id = self.novo()
        self.mover(lead_id, "REUNIAO_MARCADA")
        antes = self.contagem()
        primeira = self.data(lead_id)
        with self.sessions() as db:
            historicos = db.scalar(select(func.count(HistoricoLead.id)).where(HistoricoLead.lead_id == lead_id))
            resultado = main.fechar_contrato(lead_id, main.FechamentoContrato(valor_mensal=500), db)
            self.assertIsNotNone(db.get(Lead, lead_id).arquivado_em)
            cliente = db.get(Cliente, resultado["cliente_id"])
            self.assertEqual(cliente.lead_id, lead_id)
            self.assertEqual(historicos, db.scalar(select(func.count(HistoricoLead.id)).where(HistoricoLead.lead_id == lead_id)))
        self.assertEqual(self.data(lead_id), primeira)
        self.assertEqual(self.contagem(), antes)
        with patch.object(main, "SessionLocal", self.sessions):
            self.assertNotIn(lead_id, [lead.id for lead in main.listar_leads()])
        with self.sessions() as db:
            with self.assertRaises(HTTPException) as e:
                main.fechar_contrato(lead_id, main.FechamentoContrato(valor_mensal=500), db)
            self.assertEqual(e.exception.status_code, 404)

    def test_exclusao_preserva_indicadores_e_rejeita_novas_operacoes(self):
        lead_id = self.novo()
        self.mover(lead_id, "REUNIAO_MARCADA")
        antes = self.contagem()
        with self.sessions() as db:
            main.excluir_lead(lead_id, db)
        self.assertEqual(self.contagem(), antes)
        with patch.object(main, "SessionLocal", self.sessions):
            self.assertNotIn(lead_id, [lead.id for lead in main.listar_leads()])
        with self.sessions() as db:
            self.assertIsNotNone(db.get(Lead, lead_id).arquivado_em)
            self.assertEqual(db.scalar(select(func.count(Reuniao.id)).where(Reuniao.lead_id == lead_id)), 1)
            self.assertGreater(db.scalar(select(func.count(HistoricoLead.id)).where(HistoricoLead.lead_id == lead_id)), 0)
            for operation in [lambda: main.atualizar_fase_lead(lead_id, LeadFaseUpdate(fase="FOLLOW_UP"), db), lambda: main.registrar_prospeccao(lead_id, db), lambda: main.editar_lead(lead_id, main.LeadUpdate(nome_empresa="Outro"), db), lambda: main.cadastrar_reuniao(ReuniaoCreate(lead_id=lead_id, data_reuniao=datetime(2030, 1, 1)), db)]:
                with self.assertRaises(HTTPException) as e:
                    operation()
                self.assertEqual(e.exception.status_code, 404)

    def test_insercao_falha_desfaz_fase_prospeccao_e_historico(self):
        lead_id = self.novo()
        antes = self.contagem()
        def falhar(*_):
            raise RuntimeError("falha simulada ao inserir reuniao")
        event.listen(Reuniao, "before_insert", falhar)
        try:
            with self.assertRaises(HTTPException):
                self.mover(lead_id, "REUNIAO_MARCADA")
        finally:
            event.remove(Reuniao, "before_insert", falhar)
        with self.sessions() as db:
            lead = db.get(Lead, lead_id)
            self.assertEqual(lead.fase, "PROSPECTAR")
            self.assertIsNone(lead.prospectado_em)
            self.assertEqual(db.scalar(select(func.count(HistoricoLead.id)).where(HistoricoLead.lead_id == lead_id)), 0)
        self.assertEqual(self.contagem(), antes)

    def test_concorrencia_mesma_entrada_cria_apenas_uma_reuniao(self):
        lead_id = self.novo()
        antes = self.contagem()[0]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(self.mover, lead_id, "REUNIAO_MARCADA") for _ in range(2)]
            for future in futures:
                future.result(timeout=30)
        self.assertEqual(self.contagem()[0], antes + 1)

    def test_mes_do_agendamento_e_registros_existentes_sem_retroatividade(self):
        lead_id = self.novo("REUNIAO_MARCADA")
        with self.sessions() as db:
            antigo = Reuniao(lead_id=lead_id, data_reuniao=datetime(2025, 1, 20), criado_em=datetime(2024, 12, 31, 23, 59), status="AGENDADA")
            db.add(antigo); db.commit(); db.refresh(antigo)
            original_id = antigo.id
            dezembro = main.consultar_reunioes_mensais(2024, 12, db)["reunioes_agendadas"]
            janeiro = main.consultar_reunioes_mensais(2025, 1, db)["reunioes_agendadas"]
        self.mover(lead_id, "REUNIAO_MARCADA")
        with self.sessions() as db:
            self.assertEqual(db.scalar(select(func.count(Reuniao.id)).where(Reuniao.lead_id == lead_id)), 1)
            self.assertIsNotNone(db.get(Reuniao, original_id))
            self.assertEqual(main.consultar_reunioes_mensais(2024, 12, db)["reunioes_agendadas"], dezembro)
            self.assertEqual(main.consultar_reunioes_mensais(2025, 1, db)["reunioes_agendadas"], janeiro)
        antes = self.contagem()[0]
        self.mover(lead_id, "FOLLOW_UP")
        self.mover(lead_id, "REUNIAO_MARCADA")
        self.assertEqual(self.contagem()[0], antes + 1)


if __name__ == "__main__":
    unittest.main()
