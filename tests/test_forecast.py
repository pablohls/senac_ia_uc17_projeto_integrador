"""
Testes da Camada 2 — LSTM + surpresa (Story 3.3).

Usa séries sintéticas e poucas épocas para rodar rápido; valida o contrato
(colunas preenchidas, baseline avaliado, surpresa em pico óbvio, degradação
graciosa e reprodutibilidade via seed).
"""

import numpy as np
import pandas as pd

from src.common.config import TrendScoreParams
from src.scores.forecast import calcular_surpresa_l2
from src.scores.trend_score import trend_score_l1


def _series_com_pico(topic_id: int = 1, dias: int = 30, pico: int = 60) -> pd.DataFrame:
    """Série estável (~5/dia) com pico brutal no último dia."""
    rng = np.random.RandomState(0)
    contagens = list(5 + rng.randint(0, 2, size=dias - 1)) + [pico]
    datas = pd.date_range(start="2026-01-01", periods=dias, freq="D")
    return pd.DataFrame({"topic_id": topic_id, "data": datas, "count": contagens})


def _params(**kw) -> TrendScoreParams:
    base = dict(w=7, alpha=1.0, H=14, lambda_burst=1.0, n_min=5, k=2.5,
                seed=42, lstm_hidden_size=8, lstm_epochs=10, lstm_lr=0.01)
    base.update(kw)
    return TrendScoreParams(**base)


class TestCamada2:
    def test_metricas_preenchidas(self):
        """MAE/RMSE do baseline E da LSTM devem ser preenchidos (AC1+AC2)."""
        params = _params()
        series = _series_com_pico()
        scores = trend_score_l1(series, params)

        res, _ = calcular_surpresa_l2(series, scores, params)
        linha = res.iloc[0]

        for col in ("pred_baseline", "pred_lstm", "surprise_z",
                    "mae_baseline", "rmse_baseline", "mae_lstm", "rmse_lstm"):
            assert col in res.columns
            assert pd.notna(linha[col]), f"coluna {col} ficou NaN"

    def test_pico_gera_surpresa_e_alerta(self):
        """Pico de 5/dia para 60 deve estourar o limiar k (AC3)."""
        params = _params()
        series = _series_com_pico(pico=60)
        scores = trend_score_l1(series, params)

        res, alerts = calcular_surpresa_l2(series, scores, params)
        linha = res.iloc[0]

        assert linha["surprise_z"] > params.k
        assert bool(linha["is_anomaly"]) is True
        assert len(alerts) == 1
        assert alerts[0]["topic_id"] == 1

    def test_serie_estavel_sem_alerta(self):
        params = _params()
        rng = np.random.RandomState(1)
        contagens = 5 + rng.randint(0, 2, size=30)
        datas = pd.date_range(start="2026-01-01", periods=30, freq="D")
        series = pd.DataFrame({"topic_id": 1, "data": datas, "count": contagens})
        scores = trend_score_l1(series, params)

        _, alerts = calcular_surpresa_l2(series, scores, params)
        assert alerts == []

    def test_serie_curta_ignorada_gracioso(self):
        """Série menor que n_steps+3 é pulada sem quebrar (AC4)."""
        params = _params()
        datas = pd.date_range(start="2026-01-01", periods=5, freq="D")
        series = pd.DataFrame({"topic_id": 1, "data": datas, "count": [3] * 5})
        scores = trend_score_l1(series, params)

        res, alerts = calcular_surpresa_l2(series, scores, params)
        assert alerts == []
        assert pd.isna(res.iloc[0]["pred_lstm"])  # não previsto, mas não quebrou

    def test_reprodutibilidade_com_seed(self):
        """Mesma seed → mesmos resultados (AC da story: fixar seed)."""
        series = _series_com_pico()
        params = _params()
        scores = trend_score_l1(series, params)

        res1, _ = calcular_surpresa_l2(series, scores, params)
        res2, _ = calcular_surpresa_l2(series, scores, params)
        pd.testing.assert_frame_equal(res1, res2)
