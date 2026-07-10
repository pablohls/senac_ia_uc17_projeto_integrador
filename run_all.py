"""Orquestrador do pipeline SONAR.

Encadeia as fases offline do pipeline (o dashboard é servido à parte):

  [coleta]  →  PLN (limpeza → embeddings → clustering → doc_topics)  →  scores (séries → L1 → L2)

A coleta é OPCIONAL (--com-coleta): baixa ~4 meses de notícias com rate-limit
educado (~2h). Sem a flag, o pipeline parte do corpus congelado existente em
`dados/raw/corpus.parquet` (contrato A1 — reprodutibilidade do demo).

Uso:
  poetry run sonar                # PLN + scores a partir do corpus existente
  poetry run sonar --com-coleta   # inclui a coleta (sitemap + extract + canaltech)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

CORPUS_PATH = Path("dados/raw/corpus.parquet")


def _rodar_coleta() -> None:
    """Fase 1 — coleta completa (Olhar Digital + Canaltech)."""
    from src.coleta import canaltech, extract, sitemap

    print("=" * 60)
    print("FASE 1: COLETA (sitemap → extract → canaltech)")
    print("=" * 60)
    sitemap.main()
    extract.main(argv=[])  # argv=[] evita herdar os args do CLI `sonar`
    canaltech.main()


def main() -> None:
    """Ponto de entrada do CLI `sonar` (registrado em pyproject.toml)."""
    parser = argparse.ArgumentParser(description="Pipeline SONAR (coleta → PLN → scores)")
    parser.add_argument(
        "--com-coleta", action="store_true",
        help="Inclui a fase de coleta (~2h com rate-limit educado). "
             "Sem a flag, usa o corpus congelado existente.",
    )
    args = parser.parse_args()

    inicio = time.time()

    if args.com_coleta:
        _rodar_coleta()

    if not CORPUS_PATH.exists():
        print(f"ERRO: {CORPUS_PATH} não encontrado.")
        print("Rode com --com-coleta para coletar os dados, ou materialize o corpus antes.")
        sys.exit(1)

    # Fase 2 — PLN e modelagem de tópicos (Stories 2.1–2.4)
    from src.pln.run import main as pln_main
    pln_main()

    # Fase 3 — séries, Trend Score e surpresa LSTM (Stories 3.1–3.3)
    from src.scores.run import main as scores_main
    scores_main()

    print()
    print("=" * 60)
    print(f"PIPELINE COMPLETO EM {time.time() - inicio:.1f}s")
    print("Dashboard: poetry run streamlit run src/dashboard/app.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
