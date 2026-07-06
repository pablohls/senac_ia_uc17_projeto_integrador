"""
Testes do Trend Score Camada 1 (Story 3.2 — ver ADR-001).

Cenários sintéticos com resposta conhecida: um tópico em surto DEVE ranquear
acima de um tópico estável; as guardas (n_min, is_new) devem funcionar.
"""

import numpy as np
import pandas as pd
import pytest

from src.common.config import TrendScoreParams
from src.scores.trend_score import trend_score_l1


def _serie(topic_id: int, contagens: list[int], inicio: str = "2026-01-01") -> pd.DataFrame:
    datas = pd.date_range(start=inicio, periods=len(contagens), freq="D")
    return pd.DataFrame({"topic_id": topic_id, "data": datas, "count": contagens})


@pytest.fixture
def params():
    # w=7 / H=14 para caber em séries curtas de teste
    return TrendScoreParams(w=7, alpha=1.0, H=14, lambda_burst=1.0, n_min=5, k=2.5)


class TestTrendScoreL1:
    def test_surto_ranqueia_acima_de_estavel(self, params):
        """Tópico que explode na janela recente deve ter score maior."""
        dias = 28
        estavel = _serie(1, [3] * dias)
        # surto: 3/dia no histórico, 15/dia nos últimos 7 dias
        surto = _serie(2, [3] * (dias - 7) + [15] * 7)
        series = pd.concat([estavel, surto], ignore_index=True)

        res = trend_score_l1(series, params)

        score_surto = res.loc[res["topic_id"] == 2, "trend_score"].iloc[0]
        score_estavel = res.loc[res["topic_id"] == 1, "trend_score"].iloc[0]
        assert score_surto > score_estavel
        assert res.iloc[0]["topic_id"] == 2  # ordenado por score desc

    def test_growth_com_suavizacao_laplace(self, params):
        """P=0 não pode explodir (divisão por zero) — alpha suaviza."""
        # tópico só existe nos últimos 7 dias (P = 0)
        novo = _serie(1, [0] * 14 + [10] * 7)
        res = trend_score_l1(novo, params)

        assert np.isfinite(res.iloc[0]["growth"])
        assert res.iloc[0]["growth"] > 1

    def test_badge_is_new(self, params):
        """Tópico sem docs na janela anterior e recém-nascido → is_new."""
        novo = _serie(1, [0] * 18 + [8, 9, 10])
        res = trend_score_l1(novo, params)
        assert bool(res.iloc[0]["is_new"]) is True

    def test_topico_antigo_nao_e_new(self, params):
        antigo = _serie(1, [5] * 28)
        res = trend_score_l1(antigo, params)
        assert bool(res.iloc[0]["is_new"]) is False

    def test_guarda_n_min(self, params):
        """Tópico com R < n_min não entra no ranking (score -inf, sem rank)."""
        fraco = _serie(1, [0] * 21 + [1, 0, 0, 1, 0, 0, 1])  # R = 3 < n_min = 5
        forte = _serie(2, [3] * 28)
        series = pd.concat([fraco, forte], ignore_index=True)

        res = trend_score_l1(series, params)

        linha_fraco = res[res["topic_id"] == 1].iloc[0]
        assert bool(linha_fraco["support_ok"]) is False
        assert linha_fraco["trend_score"] == -np.inf
        assert pd.isna(linha_fraco["rank"])

        linha_forte = res[res["topic_id"] == 2].iloc[0]
        assert bool(linha_forte["support_ok"]) is True
        assert linha_forte["rank"] == 1

    def test_z_zero_sem_historico(self, params):
        """Sem pontos no horizonte H, z deve ser 0 (sem base de comparação)."""
        curta = _serie(1, [8] * 7)  # só a janela recente existe
        res = trend_score_l1(curta, params)
        assert res.iloc[0]["z"] == 0.0

    def test_t_ref_congela_o_tempo(self, params):
        """Com t_ref no passado, dados futuros não influenciam (sem leakage)."""
        serie = _serie(1, [3] * 21 + [50] * 7)  # surto na última semana
        t_passado = pd.Timestamp("2026-01-21")  # antes do surto

        res_passado = trend_score_l1(serie, params, t_ref=t_passado)
        res_presente = trend_score_l1(serie, params)

        assert res_passado.iloc[0]["R"] < res_presente.iloc[0]["R"]
        assert res_passado.iloc[0]["trend_score"] < res_presente.iloc[0]["trend_score"]

    def test_determinismo(self, params):
        series = _serie(1, list(range(28)))
        res1 = trend_score_l1(series, params)
        res2 = trend_score_l1(series, params)
        pd.testing.assert_frame_equal(res1, res2)
