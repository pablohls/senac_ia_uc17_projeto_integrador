"""Coleta da segunda fonte (Canaltech) e mesclagem ao corpus A1 (Story 1.4).

Módulo de **orquestração fino**: reaproveita o listing de URLs do Canaltech
(`sitemap.listar_urls_canaltech`), a extração de texto da Story 1.3
(`extract.extrair_artigos`) e a mesclagem deduplicada (`extract.mesclar_corpus`).
O resultado é um `corpus.parquet` **multi-fonte** (`olhar_digital` + `canaltech`),
mantendo o mesmo schema A1 (AC2) e sem URLs duplicadas (AC3).
"""

from __future__ import annotations

import logging

from src.coleta.extract import CAMINHO_CORPUS, extrair_artigos, mesclar_corpus
from src.coleta.sitemap import listar_urls_canaltech
from src.common.config import load_config
from src.common.io import atualizar_manifest, ler_parquet, salvar_parquet

logger = logging.getLogger(__name__)


def main() -> None:
    """Coleta o Canaltech, extrai o texto e mescla ao corpus A1 existente."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config()

    urls = listar_urls_canaltech(config)
    print(f"[i] {len(urls)} URLs do Canaltech na janela.")

    corpus_canaltech = extrair_artigos(urls, config)
    print(f"[i] {len(corpus_canaltech)} artigos extraídos do Canaltech.")

    atual = ler_parquet(CAMINHO_CORPUS) if CAMINHO_CORPUS.exists() else None
    combinado = mesclar_corpus(atual, corpus_canaltech)

    destino = salvar_parquet(combinado, CAMINHO_CORPUS)
    atualizar_manifest(
        "coleta",
        n_docs=len(combinado),
        stage_version="1.4",
        params={"canaltech.meses": config.coleta.canaltech.meses},
    )

    print(f"[✓] Corpus multi-fonte salvo em {destino} ({len(combinado)} artigos)")
    if not combinado.empty:
        print("    Por fonte:")
        for fonte, n in combinado["fonte"].value_counts().items():
            print(f"      {fonte}: {n}")
        print(f"    URLs duplicadas: {int(combinado['url'].duplicated().sum())} (deve ser 0)")


if __name__ == "__main__":
    main()
