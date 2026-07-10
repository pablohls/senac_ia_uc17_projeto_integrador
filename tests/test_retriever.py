"""
Testes do retriever RAG (Story 5.4 — ver ADR-002 §Feature B).

Matriz sintética pequena + encoder dublado (sem download de modelo, sem rede):
asserção de que os top_k são os de maior cosseno, vêm com metadados de citação
e de que a ausência da base degrada para lista vazia sem exceção.
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import src.rag.retriever as retriever_mod
from src.rag.retriever import limpar_cache, retrieve, top_k_cosseno


@pytest.fixture(autouse=True)
def _cache_limpo():
    """Isola o cache de módulo entre os testes."""
    limpar_cache()
    yield
    limpar_cache()


@pytest.fixture
def base_sintetica(tmp_path, monkeypatch):
    """Matriz 4×3 com direções conhecidas + índice + corpus meta."""
    matriz = np.array(
        [
            [1.0, 0.0, 0.0],   # d1 — alinhado ao eixo x
            [0.9, 0.1, 0.0],   # d2 — quase x
            [0.0, 1.0, 0.0],   # d3 — eixo y
            [0.0, 0.0, 1.0],   # d4 — eixo z
        ],
        dtype=np.float32,
    )
    np.save(tmp_path / "embeddings.npy", matriz)
    pd.DataFrame({"doc_id": ["d1", "d2", "d3", "d4"], "row_idx": range(4)}).to_parquet(
        tmp_path / "embeddings_index.parquet", index=False
    )
    pd.DataFrame(
        {
            "doc_id": ["d1", "d2", "d3", "d4"],
            "titulo": ["Artigo 1", "Artigo 2", "Artigo 3", "Artigo 4"],
            "url": ["u1", "u2", "u3", "u4"],
            "fonte": ["olhar_digital"] * 4,
        }
    ).to_parquet(tmp_path / "corpus.parquet", index=False)

    monkeypatch.setattr(retriever_mod, "EMBEDDINGS_PATH", str(tmp_path / "embeddings.npy"))
    monkeypatch.setattr(retriever_mod, "INDEX_PATH", str(tmp_path / "embeddings_index.parquet"))
    monkeypatch.setattr(retriever_mod, "CORPUS_PATH", str(tmp_path / "corpus.parquet"))
    return matriz


def _encoder_dublado(vetor: np.ndarray):
    """Encoder falso: sempre devolve `vetor` para qualquer pergunta."""
    enc = MagicMock()
    enc.encode.return_value = vetor
    return enc


class TestTopKCosseno:
    def test_ordena_por_maior_cosseno(self):
        matriz = np.eye(3, dtype=np.float32)
        vetor = np.array([0.9, 0.1, 0.0], dtype=np.float32)
        indices, scores = top_k_cosseno(vetor, matriz, k=2)
        assert list(indices) == [0, 1]
        assert scores[0] > scores[1]

    def test_k_maior_que_base_nao_estoura(self):
        matriz = np.eye(2, dtype=np.float32)
        indices, _ = top_k_cosseno(np.array([1.0, 0.0]), matriz, k=10)
        assert len(indices) == 2


class TestRetrieve:
    def test_top_k_por_cosseno_com_metadados(self, base_sintetica):
        """AC2/AC3: pergunta 'na direção x' → d1 e d2 primeiro, com citação."""
        with patch.object(
            retriever_mod, "_obter_encoder",
            return_value=_encoder_dublado(np.array([1.0, 0.05, 0.0], dtype=np.float32)),
        ):
            res = retrieve("pergunta qualquer", top_k=2)

        assert [r["doc_id"] for r in res] == ["d1", "d2"]
        assert res[0]["score"] >= res[1]["score"]
        assert res[0]["titulo"] == "Artigo 1"
        assert set(res[0]) == {"doc_id", "titulo", "url", "fonte", "score"}

    def test_top_k_default_vem_da_config(self, base_sintetica):
        """AC2: sem top_k explícito, usa config.insight.rag_top_k (limitado à base)."""
        from src.common.config import config

        with patch.object(
            retriever_mod, "_obter_encoder",
            return_value=_encoder_dublado(np.array([1.0, 0.0, 0.0], dtype=np.float32)),
        ):
            res = retrieve("pergunta")
        assert len(res) == min(config.insight.rag_top_k, 4)

    def test_base_ausente_devolve_vazio_sem_excecao(self, tmp_path, monkeypatch):
        """AC4: sem embeddings.npy → [] com log, nunca exceção."""
        monkeypatch.setattr(retriever_mod, "EMBEDDINGS_PATH", str(tmp_path / "nao_existe.npy"))
        monkeypatch.setattr(retriever_mod, "INDEX_PATH", str(tmp_path / "nao_existe.parquet"))
        assert retrieve("pergunta") == []

    def test_indice_desalinhado_devolve_vazio(self, base_sintetica, tmp_path, monkeypatch):
        """AC4: índice com nº de linhas diferente da matriz → [] com log."""
        pd.DataFrame({"doc_id": ["d1"], "row_idx": [0]}).to_parquet(
            tmp_path / "indice_torto.parquet", index=False
        )
        monkeypatch.setattr(retriever_mod, "INDEX_PATH", str(tmp_path / "indice_torto.parquet"))
        assert retrieve("pergunta") == []

    def test_falha_do_encoder_devolve_vazio(self, base_sintetica):
        """AC4: exceção interna (encoder) não propaga."""
        with patch.object(retriever_mod, "_obter_encoder", side_effect=RuntimeError("boom")):
            assert retrieve("pergunta") == []

    def test_encoder_carrega_uma_unica_vez(self, base_sintetica):
        """Should-fix @po: o modelo ST é construído UMA vez para N consultas."""
        construtor = MagicMock(
            return_value=_encoder_dublado(np.array([1.0, 0.0, 0.0], dtype=np.float32))
        )
        with patch("sentence_transformers.SentenceTransformer", construtor):
            retrieve("primeira")
            retrieve("segunda")
            retrieve("terceira")
        assert construtor.call_count == 1
