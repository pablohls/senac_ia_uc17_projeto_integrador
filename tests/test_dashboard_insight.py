"""
Testes do painel Analista IA no dashboard (Story 5.3 — AC2/AC4/AC5).

Cobrem os dois caminhos: A5 presente (label_llm substitui c-TF-IDF) e A5
ausente/vazio (dashboard idêntico ao pré-Fase 5). Smoke com AppTest roda o
app.py real e garante ausência de exceção nos dois cenários.
"""

from pathlib import Path

import pandas as pd
import pytest

from src.dashboard.insight import BRIEFINGS_PATH, aplicar_insight, carregar_briefings

APP_PATH = "src/dashboard/app.py"


@pytest.fixture
def df_ranking():
    return pd.DataFrame(
        {
            "topic_id": [2, 1],
            "label": ["ia openai", "iphone apple"],
            "trend_score": [5.0, 1.0],
        }
    )


@pytest.fixture
def briefings():
    return pd.DataFrame(
        {
            "topic_id": [2],
            "label_llm": ["Avanços da OpenAI em IA"],
            "why_summary": ["Lançamentos recentes dominaram o noticiário."],
            "model_name": ["qwen2.5:14b"],
            "generated_at": ["2026-07-08T00:00:00+00:00"],
        }
    )


class TestCarregarBriefings:
    def test_arquivo_ausente_devolve_none(self, tmp_path):
        assert carregar_briefings(tmp_path / "nao_existe.parquet") is None

    def test_arquivo_vazio_devolve_none(self, tmp_path, briefings):
        caminho = tmp_path / "vazio.parquet"
        briefings.head(0).to_parquet(caminho, index=False)
        assert carregar_briefings(caminho) is None

    def test_arquivo_presente_devolve_df(self, tmp_path, briefings):
        caminho = tmp_path / "briefings.parquet"
        briefings.to_parquet(caminho, index=False)
        df = carregar_briefings(caminho)
        assert df is not None and len(df) == 1


class TestAplicarInsight:
    def test_com_a5_prefere_label_llm(self, df_ranking, briefings):
        """AC2/AC3: label_llm substitui o c-TF-IDF; why_summary disponível."""
        df, tem_insight = aplicar_insight(df_ranking, briefings)
        assert tem_insight is True
        assert df.loc[df["topic_id"] == 2, "label"].iloc[0] == "Avanços da OpenAI em IA"
        assert "why_summary" in df.columns

    def test_topico_sem_briefing_mantem_ctfidf(self, df_ranking, briefings):
        """Join how=left: tópico fora do A5 preserva o label original."""
        df, _ = aplicar_insight(df_ranking, briefings)
        assert df.loc[df["topic_id"] == 1, "label"].iloc[0] == "iphone apple"

    def test_label_llm_vazio_cai_no_fallback(self, df_ranking, briefings):
        briefings.loc[0, "label_llm"] = "  "
        df, _ = aplicar_insight(df_ranking, briefings)
        assert df.loc[df["topic_id"] == 2, "label"].iloc[0] == "ia openai"

    def test_sem_a5_devolve_df_intacto(self, df_ranking):
        """AC2/AC4: briefings=None ⇒ mesmo df, tem_insight=False (zero regressão)."""
        df, tem_insight = aplicar_insight(df_ranking, None)
        assert tem_insight is False
        assert df is df_ranking  # intacto, nem cópia
        assert "label_llm" not in df.columns


# ---------------------------------------------------------------------------
# Smoke E2E com AppTest (roda o app.py real; requer artefatos do repo)
# ---------------------------------------------------------------------------
_tem_artefatos = Path("dados/scores/scores.parquet").exists()


@pytest.mark.skipif(not _tem_artefatos, reason="artefatos do pipeline ausentes")
class TestAppSmoke:
    def _rodar_app(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(APP_PATH, default_timeout=60)
        at.run()
        assert not at.exception, f"app.py levantou exceção: {at.exception}"
        return at

    def test_app_roda_sem_erros_com_a5(self):
        """AC4 (cenário com A5): app real sobe sem exceção."""
        if not Path(BRIEFINGS_PATH).exists():
            pytest.skip("A5 ausente neste ambiente")
        self._rodar_app()

    def test_app_roda_sem_erros_sem_a5(self, monkeypatch):
        """AC4 (cenário sem A5): remove o A5 da visão do app → dashboard pré-Fase 5."""
        import streamlit as st

        import src.dashboard.insight as insight_mod

        # Sem A5: carregar_briefings devolve None independente do disco.
        monkeypatch.setattr(insight_mod, "carregar_briefings", lambda *a, **k: None)
        st.cache_data.clear()  # invalida o cache do load_artifacts entre cenários
        try:
            self._rodar_app()
        finally:
            st.cache_data.clear()  # não vazar o cenário "sem A5" para outros testes
