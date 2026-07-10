"""Recuperador semântico do RAG (Story 5.4 — ADR-002 §Feature B).

Reúso (IDS — REUSE > CREATE): a matriz `dados/processed/embeddings.npy` e o
índice `embeddings_index.parquet` já foram produzidos pela Fase 2 — aqui só
comparamos a pergunta com eles. A pergunta é embeddada com o MESMO modelo
Sentence-Transformers do corpus (`config.embedding_model`); a similaridade é
o cosseno (vetores normalizados → produto interno).

Caches (should-fix @po): o encoder e a base ficam em cache de módulo — o
carregamento do modelo ST é o passo lento e NÃO pode acontecer a cada consulta.

Degradação graciosa (AC4): base ausente ou qualquer falha ⇒ lista vazia com
log de aviso — nunca exceção não tratada (a Story 5.5 mostra "sem base").
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from src.common.config import config

logger = logging.getLogger(__name__)

# Artefatos reutilizados (Fase 2 + corpus A1). Monkeypatcháveis nos testes.
EMBEDDINGS_PATH = "dados/processed/embeddings.npy"
INDEX_PATH = "dados/processed/embeddings_index.parquet"
CORPUS_PATH = "dados/raw/corpus.parquet"

# Cache da base carregada: (matriz normalizada float32, metadados por linha).
_base_cache: tuple[np.ndarray, pd.DataFrame] | None = None


def limpar_cache() -> None:
    """Descarta a base em cache (uso em testes/recarga de artefatos)."""
    global _base_cache
    _base_cache = None
    _obter_encoder.cache_clear()


@lru_cache(maxsize=1)
def _obter_encoder():
    """Carrega o modelo ST UMA vez (cache) — mesmo modelo do corpus (AC2)."""
    from sentence_transformers import SentenceTransformer

    logger.info("Carregando encoder %s (uma única vez)...", config.embedding_model)
    return SentenceTransformer(config.embedding_model)


def _normalizar(matriz: np.ndarray) -> np.ndarray:
    """Normaliza linhas para norma 1 (cosseno vira produto interno)."""
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    normas[normas == 0] = 1.0  # linha nula permanece nula (score 0)
    return matriz / normas


def _carregar_base() -> tuple[np.ndarray, pd.DataFrame] | None:
    """Carrega (com cache) a matriz normalizada e os metadados de citação.

    Alinha `embeddings.npy` ↔ `embeddings_index.parquet` por posição
    (`row_idx`) e junta os metadados do corpus A1 (`titulo`, `url`, `fonte`).
    Retorna ``None`` se os artefatos faltarem ou estiverem desalinhados.
    """
    global _base_cache
    if _base_cache is not None:
        return _base_cache

    caminho_emb, caminho_idx = Path(EMBEDDINGS_PATH), Path(INDEX_PATH)
    if not caminho_emb.exists() or not caminho_idx.exists():
        logger.warning(
            "Base de embeddings ausente (%s / %s) — RAG sem base para responder.",
            caminho_emb, caminho_idx,
        )
        return None

    matriz = np.load(caminho_emb)
    indice = pd.read_parquet(caminho_idx).sort_values("row_idx")
    if len(indice) != matriz.shape[0]:
        logger.warning(
            "Índice (%d) desalinhado da matriz (%d) — RAG desativado.",
            len(indice), matriz.shape[0],
        )
        return None

    corpus_meta = pd.read_parquet(
        Path(CORPUS_PATH), columns=["doc_id", "titulo", "url", "fonte"]
    )
    meta = indice.merge(corpus_meta, on="doc_id", how="left")

    _base_cache = (_normalizar(matriz.astype(np.float32)), meta.reset_index(drop=True))
    return _base_cache


def top_k_cosseno(
    vetor: np.ndarray, matriz_norm: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Índices e scores dos ``k`` maiores cossenos entre `vetor` e a matriz.

    Args:
        vetor: embedding da pergunta (1D, não precisa estar normalizado).
        matriz_norm: matriz com linhas já normalizadas.
        k: quantos resultados devolver.

    Returns:
        ``(indices, scores)`` ordenados por score decrescente.
    """
    v = vetor.astype(np.float32)
    norma = np.linalg.norm(v)
    if norma > 0:
        v = v / norma
    scores = matriz_norm @ v
    k = min(k, len(scores))
    ordem = np.argsort(scores)[::-1][:k]
    return ordem, scores[ordem]


def retrieve(pergunta: str, top_k: int | None = None) -> list[dict]:
    """Recupera os artigos mais semelhantes à pergunta (AC2/AC3).

    Args:
        pergunta: texto em PT-BR.
        top_k: nº de resultados; default ``config.insight.rag_top_k``.

    Returns:
        Lista de ``{doc_id, titulo, url, fonte, score}`` ordenada por
        similaridade decrescente — ou ``[]`` em qualquer falha (AC4).
    """
    try:
        base = _carregar_base()
        if base is None:
            return []
        matriz_norm, meta = base

        k = top_k if top_k is not None else config.insight.rag_top_k
        vetor = _obter_encoder().encode(pergunta, convert_to_numpy=True)
        indices, scores = top_k_cosseno(vetor, matriz_norm, k)

        resultados = []
        for idx, score in zip(indices, scores):
            linha = meta.iloc[int(idx)]
            resultados.append(
                {
                    "doc_id": linha["doc_id"],
                    "titulo": linha["titulo"],
                    "url": linha["url"],
                    "fonte": linha["fonte"],
                    "score": float(score),
                }
            )
        return resultados
    except Exception as exc:  # noqa: BLE001 — degradação graciosa é o contrato (AC4)
        logger.warning(
            "Falha no retriever (%s: %s) — devolvendo lista vazia.",
            type(exc).__name__, exc,
        )
        return []
