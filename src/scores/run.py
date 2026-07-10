"""
Runner da Fase 3 — séries temporais, Trend Score (L1) e surpresa LSTM (L2).

Encadeia as Stories 3.1 → 3.2 → 3.3 sobre o contrato A3 produzido pela Fase 2:
  entrada: dados/topics/doc_topics.parquet  {doc_id, data, topic_id[, probabilidade]}
  saídas:  dados/scores/series.parquet      {topic_id, data, count, count_weekly}
           dados/scores/scores.parquet      (L1 + colunas L2)
           dados/scores/alerts.json         (anomalias da Camada 2)

Uso: poetry run python -m src.scores.run
"""

from __future__ import annotations

import logging
import time

from src.common.config import load_config
from src.common.io import ler_parquet, salvar_parquet, atualizar_manifest
from src.scores.series import montar_series
from src.scores.trend_score import trend_score_l1
from src.scores.forecast import calcular_surpresa_l2, salvar_alertas

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DOC_TOPICS_PATH = "dados/topics/doc_topics.parquet"
CORPUS_PATH = "dados/raw/corpus.parquet"
SERIES_PATH = "dados/scores/series.parquet"
SCORES_PATH = "dados/scores/scores.parquet"


def _filtrar_fontes_temporais(doc_topics, fontes_confiaveis):
    """Mantém na análise temporal só os docs de fontes com data confiável.

    Fontes fora da lista (ex.: Canaltech, cuja data vem do <lastmod> do sitemap
    e distorce as séries — DATA-001) seguem no corpus/tópicos/RAG, mas não contam
    aqui. `fontes_confiaveis=None` desativa o filtro (usa todas as fontes).
    """
    if not fontes_confiaveis:
        return doc_topics
    corpus = ler_parquet(CORPUS_PATH)
    fonte_por_doc = corpus.set_index("doc_id")["fonte"]
    df = doc_topics.copy()
    df["_fonte"] = df["doc_id"].map(fonte_por_doc)
    antes = len(df)
    df = df[df["_fonte"].isin(fontes_confiaveis)].drop(columns="_fonte")
    logger.info(
        "  Filtro temporal (DATA-001): %d de %d docs mantidos — fontes confiáveis=%s",
        len(df), antes, fontes_confiaveis,
    )
    return df


def main() -> None:
    """Executa toda a pipeline da Fase 3."""
    config = load_config()
    inicio_total = time.time()

    logger.info("=" * 60)
    logger.info("INICIANDO PIPELINE DA FASE 3 (scores)")
    logger.info("=" * 60)

    # ---- Story 3.1 — Séries temporais por tópico ----
    logger.info("--- Story 3.1: Séries temporais por tópico ---")
    doc_topics = ler_parquet(DOC_TOPICS_PATH)
    logger.info("  doc_topics: %d linhas", len(doc_topics))

    doc_topics = _filtrar_fontes_temporais(
        doc_topics, config.analise_temporal.fontes_confiaveis
    )

    series = montar_series(doc_topics)
    caminho_series = salvar_parquet(series, SERIES_PATH)
    logger.info("  ✓ Série persistida: %s (%d linhas, %d tópicos)",
                caminho_series, len(series), series["topic_id"].nunique())

    # ---- Story 3.2 — Trend Score Camada 1 (estatístico) ----
    logger.info("--- Story 3.2: Trend Score Camada 1 ---")
    scores = trend_score_l1(series, config.trend_score)
    logger.info("  ✓ Scores calculados: %d tópicos", len(scores))

    top_5 = scores.head(5)
    logger.info("  Top 5 tendências (L1):")
    for _, row in top_5.iterrows():
        badge = "[NOVO]" if row["is_new"] else ""
        logger.info("    - Tópico %s: score=%.2f %s", row["topic_id"], row["trend_score"], badge)

    # ---- Story 3.3 — Camada 2 (LSTM + surpresa), degradação graciosa ----
    logger.info("--- Story 3.3: Camada 2 (LSTM + Surpresa) ---")
    scores_final, alerts = calcular_surpresa_l2(series, scores, config.trend_score)
    if alerts:
        logger.info("  ⚠ %d anomalias detectadas", len(alerts))
    salvar_alertas(alerts)  # grava sempre (lista vazia = sem anomalias)

    caminho_scores = salvar_parquet(scores_final, SCORES_PATH)
    logger.info("  ✓ Scores persistidos (L1+L2): %s", caminho_scores)

    # ---- Manifesto transversal de reprodutibilidade (contrato A1) ----
    atualizar_manifest(
        "scores",
        stage_version="3.1-3.3",
        params={
            "trend_score": config.trend_score.model_dump(),
            "fontes_temporais": config.analise_temporal.fontes_confiaveis,
        },
        extras={"n_alerts": len(alerts)},
    )

    logger.info("=" * 60)
    logger.info("PIPELINE DA FASE 3 CONCLUÍDA EM %.1fs", time.time() - inicio_total)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
