"""
Testes do Analista IA batch (Story 5.2 — contrato A5, ver ADR-002 §Feature A).

`chat()` é sempre mockado (determinístico, sem rede). Cobrem: seleção dos
tópicos em ascensão, schema A5, fallback por tópico e falha global do LLM
(pipeline termina sem quebrar e sem gravar A5).
"""

from unittest.mock import patch

import pandas as pd
import pytest

from src.insight.analista import (
    gerar_briefing,
    limpar_label,
    montar_contexto,
    selecionar_topicos_ascensao,
)
from src.insight.run import SCHEMA_A5


@pytest.fixture
def scores():
    return pd.DataFrame(
        {
            "topic_id": [-1, 1, 2, 3],
            "trend_score": [9.9, 1.0, 5.0, 3.0],
            "support_ok": [True, True, True, False],
        }
    )


@pytest.fixture
def topic_info():
    return pd.DataFrame(
        {
            "topic_id": [-1, 1, 2, 3],
            "label": ["outliers", "iphone apple", "ia openai", "chip nvidia"],
        }
    )


@pytest.fixture
def doc_topics():
    return pd.DataFrame(
        {
            "doc_id": ["d1", "d2", "d3", "d4"],
            "topic_id": [2, 2, 2, 1],
            "probabilidade": [0.9, 0.8, 0.7, 0.95],
        }
    )


@pytest.fixture
def corpus():
    return pd.DataFrame(
        {
            "doc_id": ["d1", "d2", "d3", "d4"],
            "titulo": ["OpenAI lança modelo", "IA no Brasil", "Regulação da IA", "iPhone 17"],
            "texto": ["texto um " * 100, "texto dois", "texto três", "texto quatro"],
        }
    )


class TestSelecao:
    def test_exclui_outlier_e_sem_suporte_ordena_por_score(self, scores, topic_info):
        """AC1: topic_id != -1, support_ok=True, ordem trend_score desc."""
        res = selecionar_topicos_ascensao(scores, topic_info)
        assert list(res["topic_id"]) == [2, 1]  # -1 e 3 (support_ok=False) fora
        assert list(res["label"]) == ["ia openai", "iphone apple"]


class TestContexto:
    def test_top_artigos_por_probabilidade_com_titulo_e_trecho(self, doc_topics, corpus):
        """AC1: top_artigos por probabilidade; trecho vem do corpus A1 truncado."""
        from src.common.config import config

        contexto = montar_contexto(2, doc_topics, corpus)
        assert "OpenAI lança modelo" in contexto
        assert "iPhone 17" not in contexto  # doc de outro tópico
        # trecho truncado em trecho_max_chars (texto de d1 tem 900 chars)
        linhas_d1 = [ln for ln in contexto.splitlines() if "texto um" in ln]
        assert linhas_d1 and len(linhas_d1[0]) <= config.insight.trecho_max_chars + 10

    def test_respeita_limite_top_artigos(self, doc_topics, corpus):
        from src.common.config import config

        contexto = montar_contexto(2, doc_topics, corpus)
        n_blocos = len([ln for ln in contexto.splitlines() if ln and ln[0].isdigit()])
        assert n_blocos <= config.insight.top_artigos


class TestLimparLabel:
    def test_remove_aspas_e_quebras(self):
        assert limpar_label('"Alta do iPhone"\nextra') == "Alta do iPhone"

    def test_trunca_em_8_palavras(self):
        label = limpar_label("um dois três quatro cinco seis sete oito nove dez")
        assert len(label.split()) == 8


class TestGerarBriefing:
    def test_sucesso_devolve_label_e_why(self):
        """AC2: duas chamadas (rotulação + why) viram (label, why, ok=True)."""
        respostas = iter(["Prime Day pressiona iPhone", "Preços caíram nas promoções."])
        with patch("src.insight.analista.chat", side_effect=lambda *a, **k: next(respostas)):
            label, why, ok = gerar_briefing("iphone apple", "contexto")
        assert ok is True
        assert label == "Prime Day pressiona iPhone"
        assert why == "Preços caíram nas promoções."

    def test_falha_total_devolve_fallback_ctfidf(self):
        """AC5: chat() → None ⇒ label c-TF-IDF, why vazio, ok=False, sem raise."""
        with patch("src.insight.analista.chat", return_value=None):
            label, why, ok = gerar_briefing("iphone apple", "contexto")
        assert (label, why, ok) == ("iphone apple", "", False)

    def test_falha_so_no_why_mantem_label_gerado(self):
        respostas = iter(["Label bom", None])
        with patch("src.insight.analista.chat", side_effect=lambda *a, **k: next(respostas)):
            label, why, ok = gerar_briefing("iphone apple", "contexto")
        assert (label, why, ok) == ("Label bom", "", False)

    def test_usa_temperature_batch_da_config(self):
        """AC4: reprodutibilidade — temperature vem de config.insight.temperature_batch."""
        from src.common.config import config

        with patch("src.insight.analista.chat", return_value="ok") as m:
            gerar_briefing("x", "contexto")
        for call in m.call_args_list:
            assert call.kwargs["temperature"] == config.insight.temperature_batch


class TestRunGerarBriefings:
    def _com_artefatos(self, scores, topic_info, doc_topics, corpus):
        """Patch do IO para usar os fixtures em vez do disco."""
        artefatos = {
            "dados/topics/doc_topics.parquet": doc_topics,
            "dados/topics/topic_info.parquet": topic_info,
            "dados/scores/scores.parquet": scores,
            "dados/raw/corpus.parquet": corpus,
        }
        return patch("src.insight.run.ler_parquet", side_effect=lambda p: artefatos[str(p)])

    def test_schema_a5_completo(self, scores, topic_info, doc_topics, corpus):
        """AC3/AC4: colunas do contrato A5, model_name da config, ISO generated_at."""
        from src.common.config import config
        from src.insight.run import gerar_briefings

        respostas = iter(["Label A", "Why A.", "Label B", "Why B."])
        with self._com_artefatos(scores, topic_info, doc_topics, corpus):
            with patch("src.insight.analista.chat", side_effect=lambda *a, **k: next(respostas)):
                df = gerar_briefings()

        assert list(df.columns) == SCHEMA_A5
        assert len(df) == 2  # só tópicos 2 e 1
        assert (df["model_name"] == config.insight.model).all()
        assert df["generated_at"].str.contains("T").all()  # ISO-8601

    def test_llm_totalmente_indisponivel_devolve_none_sem_quebrar(
        self, scores, topic_info, doc_topics, corpus
    ):
        """AC5: falha global → None (A5 não gerado), nenhuma exceção."""
        from src.insight.run import gerar_briefings

        with self._com_artefatos(scores, topic_info, doc_topics, corpus):
            with patch("src.insight.analista.chat", return_value=None) as m:
                assert gerar_briefings() is None
        # curto-circuito: falha no 1º tópico não martela os demais (≤2 chamadas)
        assert m.call_count <= 2

    def test_fallback_parcial_mantem_linha_com_label_ctfidf(
        self, scores, topic_info, doc_topics, corpus
    ):
        """AC5: falha em UM tópico vira fallback naquela linha; A5 sai mesmo assim."""
        from src.insight.run import gerar_briefings

        # tópico 2 (1º por score) OK; tópico 1 falha nas duas chamadas
        respostas = iter(["Label A", "Why A.", None, None])
        with self._com_artefatos(scores, topic_info, doc_topics, corpus):
            with patch("src.insight.analista.chat", side_effect=lambda *a, **k: next(respostas)):
                df = gerar_briefings()

        linha_fallback = df[df["topic_id"] == 1].iloc[0]
        assert linha_fallback["label_llm"] == "iphone apple"  # c-TF-IDF preservado
        assert linha_fallback["why_summary"] == ""
        assert df[df["topic_id"] == 2].iloc[0]["label_llm"] == "Label A"
