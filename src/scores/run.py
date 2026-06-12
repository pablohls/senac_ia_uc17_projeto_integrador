"""Orquestrador da Fase 4 (Scores) — Stories 3.1 a 3.4.

Este módulo coordena a execução de todas as stories da Fase 4:
- Story 3.1: Montar séries temporais por tópico (zero-filled)
- Story 3.2: Trend Score Camada 1 (estatístico)
- Story 3.3: Trend Score Camada 2 (LSTM + baseline)
- Story 3.4: Validação por backtest

Uso (offline):
    poetry run python -m src.scores.run

Uso (integrado no pipeline):
    python -m src.scores.run (chamado por run_all.py)

Entrada (artefatos):
    - dados/topics/doc_topics.parquet (saída da Fase 3)
    - config/config.yaml (parâmetros centralizados)

Saída (artefatos):
    - dados/scores/series.parquet (Story 3.1)
    - dados/scores/scores.parquet (Stories 3.2 + 3.3)
    - dados/scores/alerts.json (Story 3.3, best-effort)
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.common.config import load_config
from src.common.io import ler_parquet, salvar_parquet
from src.scores.series import montar_series

logger = logging.getLogger(__name__)


def main() -> None:
    """Orquestrador principal da Fase 4 (scores).

    Flow:
    1. Carrega configuração (config.yaml)
    2. Lê doc_topics.parquet (entrada da Fase 3)
    3. Executa Story 3.1: montar_series (zero-fill)
    4. Persiste series.parquet
    5. (Stories 3.2, 3.3, 3.4 em desenvolvimento)

    Raises:
        FileNotFoundError: se doc_topics.parquet não existir.
        ValueError: se validação de dados falhar.
    """
    logger.info("=" * 60)
    logger.info("Fase 4 — Scores (Stories 3.1 a 3.4)")
    logger.info("=" * 60)

    # Step 1: Carrega configuração
    logger.info("Carregando configuração...")
    config = load_config()
    logger.info(f"  Config OK. Trend Score params: w={config.trend_score.w}, "
                f"alpha={config.trend_score.alpha}, H={config.trend_score.H}")

    # Step 2: Lê entrada (doc_topics da Fase 3)
    input_path = Path("dados/topics/doc_topics.parquet")
    if not input_path.exists():
        raise FileNotFoundError(
            f"Entrada não encontrada: {input_path}\n"
            "Certifique-se de que a Fase 3 (Modelagem) foi executada."
        )
    logger.info(f"Lendo {input_path}...")
    doc_topics = ler_parquet(input_path)
    logger.info(f"  ✓ {len(doc_topics)} documentos lidos")

    # Step 3: Story 3.1 — Montar séries temporais
    logger.info("\n--- Story 3.1: Montar séries temporais ---")
    try:
        series = montar_series(doc_topics, gerar_weekly=True)
        logger.info(f"  ✓ Séries montadas: {len(series)} linhas")
        logger.info(f"  Tópicos únicos: {series['topic_id'].nunique()}")
        logger.info(f"  Período: {series['data'].min()} a {series['data'].max()}")

        # Persiste
        output_path = salvar_parquet(series, "dados/scores/series.parquet")
        logger.info(f"  ✓ Persistido: {output_path}")

    except Exception as e:
        logger.error(f"  ✗ Erro na Story 3.1: {e}", exc_info=True)
        raise

    logger.info("\n" + "=" * 60)
    logger.info("Fase 4 — Stories 3.1 concluída com sucesso!")
    logger.info("(Stories 3.2, 3.3, 3.4 em desenvolvimento)")
    logger.info("=" * 60)


if __name__ == "__main__":
    # Config básico de logging (será expandido em src/common/logging.py)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s — [%(name)s] %(levelname)s: %(message)s",
    )
    main()
