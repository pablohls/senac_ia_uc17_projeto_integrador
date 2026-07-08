"""Integração do Analista IA (A5) no dashboard (Story 5.3 — ADR-002 §Feature A).

Funções puras e testáveis (padrão do `graph.py`: lógica fora do script Streamlit)
para carregar o `briefings.parquet` como artefato OPCIONAL e preferir os rótulos
do LLM aos c-TF-IDF quando disponíveis. Sem A5, o dashboard fica exatamente
como antes da Fase 5 — degradação graciosa (AC2/AC4).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

# Contrato A5 (Story 5.2). O dashboard só LÊ — nenhum cômputo pesado (NFR8).
BRIEFINGS_PATH = "dados/insight/briefings.parquet"


def carregar_briefings(caminho: str | Path = BRIEFINGS_PATH) -> pd.DataFrame | None:
    """Lê o A5 se existir e não estiver vazio; senão devolve ``None`` (opcional)."""
    p = Path(caminho)
    if not p.exists():
        return None
    df = pd.read_parquet(p)
    if df.empty:
        return None
    return df


def aplicar_insight(
    df_ranking: pd.DataFrame, briefings: pd.DataFrame | None
) -> tuple[pd.DataFrame, bool]:
    """Prefere `label_llm` sobre o `label` c-TF-IDF quando o A5 está disponível.

    Junta por `topic_id` (`how="left"`): tópicos sem briefing mantêm o label
    original; `label_llm` vazio/nulo também cai no fallback (linhas de fallback
    da Story 5.2 têm o próprio label c-TF-IDF, então nada se perde).

    Returns:
        Tupla ``(df, tem_insight)`` — ``df`` ganha as colunas `label_llm` e
        `why_summary` quando ``tem_insight=True``; caso contrário volta intacto.
    """
    if briefings is None or briefings.empty:
        return df_ranking, False

    df = df_ranking.merge(
        briefings[["topic_id", "label_llm", "why_summary"]], on="topic_id", how="left"
    )
    usar_llm = df["label_llm"].notna() & (df["label_llm"].astype(str).str.strip() != "")
    df["label"] = df["label_llm"].where(usar_llm, df["label"])
    return df, True
