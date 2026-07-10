"""
Runner da Fase 5 — Analista IA batch (Story 5.2, ADR-002 §Feature A).

Gera, para cada tópico em ascensão, um rótulo em linguagem natural e um
parágrafo "por que sobe", persistindo o contrato A5:
  entradas: dados/topics/{doc_topics,topic_info}.parquet
            dados/scores/scores.parquet
            dados/raw/corpus.parquet          (título/trecho — corpus A1)
  saída:    dados/insight/briefings.parquet   {topic_id, label_llm, why_summary,
                                               model_name, generated_at}

Degradação graciosa (AC5): falha por tópico vira fallback (label c-TF-IDF);
LLM totalmente indisponível ⇒ termina sem quebrar e SEM gravar A5 (o dashboard
segue com os labels c-TF-IDF, como antes desta fase).

Uso: poetry run python -m src.insight.run
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime

import pandas as pd

from src.common.config import config
from src.common.io import atualizar_manifest, ler_parquet, salvar_parquet
from src.insight.analista import gerar_briefing, montar_contexto, selecionar_topicos_ascensao

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DOC_TOPICS_PATH = "dados/topics/doc_topics.parquet"
TOPIC_INFO_PATH = "dados/topics/topic_info.parquet"
SCORES_PATH = "dados/scores/scores.parquet"
CORPUS_PATH = "dados/raw/corpus.parquet"
BRIEFINGS_PATH = "dados/insight/briefings.parquet"

# Colunas do contrato A5 (ADR-002).
SCHEMA_A5 = ["topic_id", "label_llm", "why_summary", "model_name", "generated_at"]


def gerar_briefings() -> pd.DataFrame | None:
    """Gera o DataFrame A5 para os tópicos em ascensão.

    Returns:
        DataFrame no schema A5, ou ``None`` se o LLM esteve totalmente
        indisponível (nenhum briefing gerado — AC5).
    """
    doc_topics = ler_parquet(DOC_TOPICS_PATH)
    topic_info = ler_parquet(TOPIC_INFO_PATH)
    scores = ler_parquet(SCORES_PATH)
    corpus = ler_parquet(CORPUS_PATH)

    ascensao = selecionar_topicos_ascensao(scores, topic_info)
    logger.info("  Tópicos em ascensão selecionados: %d", len(ascensao))

    generated_at = datetime.now(UTC).isoformat()
    linhas: list[dict] = []
    n_ok = 0
    llm_disponivel = True  # vira False na 1ª falha total → fallback direto nos demais

    for pos, row in enumerate(ascensao.itertuples(index=False), start=1):
        label_ctfidf = str(row.label)
        if llm_disponivel:
            contexto = montar_contexto(int(row.topic_id), doc_topics, corpus)
            label, why, ok = gerar_briefing(label_ctfidf, contexto)
            if ok:
                n_ok += 1
                logger.info("  [%d/%d] tópico %d → %r", pos, len(ascensao), row.topic_id, label)
            else:
                logger.warning(
                    "  [%d/%d] tópico %d: LLM falhou — fallback c-TF-IDF %r",
                    pos, len(ascensao), row.topic_id, label_ctfidf,
                )
                if n_ok == 0:
                    # Nenhum sucesso até aqui e a 1ª falha ocorreu: assume LLM
                    # fora do ar e poupa os timeouts dos tópicos restantes.
                    llm_disponivel = False
        else:
            label, why = label_ctfidf, ""

        linhas.append(
            {
                "topic_id": int(row.topic_id),
                "label_llm": label,
                "why_summary": why,
                "model_name": config.insight.model,
                "generated_at": generated_at,
            }
        )

    if n_ok == 0:
        logger.warning(
            "  LLM totalmente indisponível (%s) — A5 não será gerado; "
            "o dashboard segue com labels c-TF-IDF.",
            config.insight.base_url,
        )
        return None

    logger.info("  Briefings gerados via LLM: %d/%d (fallbacks: %d)",
                n_ok, len(ascensao), len(ascensao) - n_ok)
    return pd.DataFrame(linhas, columns=SCHEMA_A5)


def main() -> None:
    """Executa o estágio Analista IA (Fase 5 — batch)."""
    inicio_total = time.time()

    logger.info("=" * 60)
    logger.info("INICIANDO PIPELINE DA FASE 5 (insight — Analista IA)")
    logger.info("=" * 60)
    logger.info("--- Story 5.2: briefings por tópico (modelo: %s) ---", config.insight.model)

    briefings = gerar_briefings()
    if briefings is None:
        logger.info("=" * 60)
        logger.info("FASE 5 ENCERRADA SEM A5 (LLM indisponível) EM %.1fs",
                    time.time() - inicio_total)
        logger.info("=" * 60)
        return

    caminho = salvar_parquet(briefings, BRIEFINGS_PATH)
    logger.info("  ✓ Contrato A5 persistido: %s (%d tópicos)", caminho, len(briefings))

    # ---- Manifesto transversal de reprodutibilidade ----
    atualizar_manifest(
        "insight",
        stage_version="5.2",
        params={"insight": config.insight.model_dump()},
        extras={"insight_model": config.insight.model},
    )

    logger.info("=" * 60)
    logger.info("PIPELINE DA FASE 5 CONCLUÍDA EM %.1fs", time.time() - inicio_total)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
