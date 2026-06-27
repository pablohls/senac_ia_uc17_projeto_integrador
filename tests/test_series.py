"""Testes unitários para Story 3.1 — séries temporais com zero-fill.

Casos de teste cobrindo:
- AC1: série de contagem diária
- AC2: agregação semanal
- AC3: zero-fill completo
- Erros: entrada vazia, colunas faltando
- Determinismo: mesma entrada → mesma saída
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from src.scores.series import montar_series, validar_serie


class TestMontarSeries:
    """Testes da função montar_series."""

    @pytest.fixture
    def doc_topics_simples(self):
        """Fixture: dataset pequeno e determinístico (3 tópicos, 10 dias)."""
        return pd.DataFrame(
            {
                "doc_id": [
                    "doc001",
                    "doc002",
                    "doc003",
                    "doc004",
                    "doc005",
                    "doc006",
                    "doc007",
                    "doc008",
                    "doc009",
                ],
                "data": [
                    date(2026, 1, 1),
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                    date(2026, 1, 5),
                    date(2026, 1, 5),
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                    date(2026, 1, 4),
                    date(2026, 1, 5),
                ],
                "topic_id": [0, 1, 0, 1, 0, 2, 2, 2, 2],
            }
        )

    def test_ac1_contagem_diaria(self, doc_topics_simples):
        """AC1: série de contagem por dia e tópico."""
        series = montar_series(doc_topics_simples, gerar_weekly=False)

        # Verificar que topic 0 tem 3 docs: 2026-01-01 (1), 2026-01-02 (1), 2026-01-03 (1)
        t0 = series[series["topic_id"] == 0]
        assert len(t0) == 5  # 5 dias no período (1-5)
        assert t0[t0["data"] == date(2026, 1, 1)]["count"].values[0] == 1
        assert t0[t0["data"] == date(2026, 1, 2)]["count"].values[0] == 1
        assert t0[t0["data"] == date(2026, 1, 5)]["count"].values[0] == 1
        assert t0[t0["data"] == date(2026, 1, 4)]["count"].values[0] == 0  # zero-fill
        assert t0[t0["data"] == date(2026, 1, 5)]["count"].values[0] == 1

    def test_ac3_zero_fill(self, doc_topics_simples):
        """AC3: zero-fill — todos os dias do período preenchidos."""
        series = montar_series(doc_topics_simples, gerar_weekly=False)

        # Período: 2026-01-01 a 2026-01-05 (5 dias)
        # 3 tópicos → 15 linhas esperadas
        assert len(series) == 15  # 3 tópicos × 5 dias

        # Verificar que nenhum dia falta para nenhum tópico
        for topic_id in [0, 1, 2]:
            topic_series = series[series["topic_id"] == topic_id]
            datas = sorted(topic_series["data"].unique())
            assert len(datas) == 5
            assert datas[0] == date(2026, 1, 1)
            assert datas[-1] == date(2026, 1, 5)

    def test_ac2_agregacao_semanal(self, doc_topics_simples):
        """AC2: agregação semanal (count_weekly)."""
        series = montar_series(doc_topics_simples, gerar_weekly=True)

        # Deve ter coluna count_weekly
        assert "count_weekly" in series.columns

        # Verificar valores: toda semana deve ter um valor agregado
        t0 = series[series["topic_id"] == 0]
        # Jan 1-5, 2026 = semana que termina em Jan 5 (Sunday)
        # Esperado: 3 docs em topic 0 na semana
        weekly_sum = t0["count_weekly"].iloc[0]  # todas as linhas da semana têm o mesmo weekly
        assert weekly_sum == 3

    def test_determinismo(self, doc_topics_simples):
        """Determinismo: mesma entrada → mesma saída."""
        s1 = montar_series(doc_topics_simples, gerar_weekly=False)
        s2 = montar_series(doc_topics_simples, gerar_weekly=False)

        pd.testing.assert_frame_equal(s1, s2)

    def test_ordenacao(self, doc_topics_simples):
        """Ordenação: series está ordenada por topic_id, depois data."""
        series = montar_series(doc_topics_simples, gerar_weekly=False)

        # Verificar que está ordenado
        topics_orden = series["topic_id"].values
        datas_orden = series["data"].values

        for i in range(len(topics_orden) - 1):
            if topics_orden[i] == topics_orden[i + 1]:
                assert datas_orden[i] <= datas_orden[i + 1]

    def test_erro_vazio(self):
        """Erro: doc_topics vazio."""
        empty_df = pd.DataFrame(columns=["doc_id", "data", "topic_id"])
        with pytest.raises(ValueError, match="não pode estar vazio"):
            montar_series(empty_df)

    def test_erro_colunas_faltando(self):
        """Erro: colunas obrigatórias faltando."""
        df = pd.DataFrame({"doc_id": ["doc001"], "data": [date(2026, 1, 1)]})
        with pytest.raises(ValueError, match="Colunas obrigatórias faltando"):
            montar_series(df)

    def test_com_datas_strings_iso(self):
        """Flexibilidade: aceita datas como strings ISO."""
        df = pd.DataFrame(
            {
                "doc_id": ["doc001", "doc002"],
                "data": ["2026-01-01", "2026-01-02"],
                "topic_id": [0, 0],
            }
        )
        series = montar_series(df, gerar_weekly=False)

        assert len(series) == 2
        assert series["count"].sum() == 2

    def test_com_outliers_topic_minus_1(self):
        """Flexibilidade: tópico -1 (outliers) é tratado como qualquer outro."""
        df = pd.DataFrame(
            {
                "doc_id": ["doc001", "doc002", "doc003"],
                "data": [date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 2)],
                "topic_id": [0, -1, -1],
            }
        )
        series = montar_series(df, gerar_weekly=False)

        # Deve ter 2 tópicos: 0 e -1
        assert set(series["topic_id"].unique()) == {0, -1}

        # Período: 1-2 de janeiro
        # 2 tópicos × 2 dias = 4 linhas
        assert len(series) == 4


class TestValidarSerie:
    """Testes do validador validar_serie."""

    def test_serie_valida(self):
        """Serie bem-formada passa em todas as validações."""
        series = pd.DataFrame(
            {
                "topic_id": [0, 0, 0, 1, 1, 1],
                "data": [
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                    date(2026, 1, 5),
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                    date(2026, 1, 5),
                ],
                "count": [1, 0, 2, 0, 1, 1],
                "count_weekly": [3, 3, 3, 2, 2, 2],
            }
        )
        resultado = validar_serie(series)

        assert resultado["zero_filled"] is False
        assert resultado["soma_consistente"] is True
        assert resultado["tipos_corretos"] is True

    def test_serie_vazia(self):
        """Serie vazia falha em todas validações."""
        series = pd.DataFrame()
        resultado = validar_serie(series)

        assert all(v is False for v in resultado.values())

    def test_nao_zero_filled(self):
        """Serie com gaps (não zero-filled) falha."""
        series = pd.DataFrame(
            {
                "topic_id": [0, 0, 1, 1],
                "data": [
                    date(2026, 1, 1),
                    date(2026, 1, 5),  # falta 1-2
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                ],
                "count": [1, 2, 1, 1],
            }
        )
        resultado = validar_serie(series)

        assert resultado["zero_filled"] is False


class TestIntegration:
    """Testes de integração (flow end-to-end)."""

    def test_flow_completo(self):
        """Flow completo: gerar → validar → verificar saída."""
        # Simular entrada (típica da Fase 3/Modelagem)
        doc_topics = pd.DataFrame(
            {
                "doc_id": [f"doc{i:03d}" for i in range(1, 21)],
                "data": [
                    date(2026, 1, 1),
                    date(2026, 1, 1),
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                    date(2026, 1, 2),
                    date(2026, 1, 5),
                    date(2026, 1, 5),
                    date(2026, 1, 5),
                    date(2026, 1, 5),
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                    date(2026, 1, 5),
                    date(2026, 1, 4),
                    date(2026, 1, 5),
                    date(2026, 1, 1),
                    date(2026, 1, 2),
                    date(2026, 1, 5),
                    date(2026, 1, 4),
                    date(2026, 1, 5),
                    date(2026, 1, 1),
                ],
                "topic_id": [0] * 9 + [1] * 5 + [2] * 6,
            }
        )

        # Step 1: montar series
        series = montar_series(doc_topics, gerar_weekly=True)

        # Step 2: validar
        val = validar_serie(series)

        # Step 3: asserções
        assert val["zero_filled"]
        assert val["soma_consistente"]
        assert val["tipos_corretos"]

        # AC1: série de contagem diária
        assert len(series[series["topic_id"] == 0]) == 5  # 5 dias
        assert series[series["topic_id"] == 0]["count"].sum() == 9  # 9 docs

        # AC2: agregação semanal
        assert "count_weekly" in series.columns

        # AC3: zero-fill
        n_topics = len(doc_topics["topic_id"].unique())
        n_dias = (doc_topics["data"].max() - doc_topics["data"].min()).days + 1
        assert len(series) == n_topics * n_dias
