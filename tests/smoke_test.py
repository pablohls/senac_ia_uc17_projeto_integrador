"""Smoke test do ambiente TrendRadar.

O "checklist de obra": antes de qualquer integrante começar a fase dele, este
teste confirma que a fundação está de pé — bibliotecas instaladas, GPU detectada
(ou modo CPU avisado, sem falhar) e leitura/escrita de Parquet funcionando.

Rodar com:  poetry run pytest tests/smoke_test.py -s
"""

from __future__ import annotations

import pandas as pd


def test_imports_principais() -> None:
    """(a) As bibliotecas centrais do pipeline importam sem erro."""
    import bertopic  # noqa: F401
    import numpy  # noqa: F401
    import sentence_transformers  # noqa: F401
    import torch  # noqa: F401


def test_gpu_disponivel() -> None:
    """(b) Reporta se a GPU foi detectada. NÃO falha em modo CPU (apenas avisa)."""
    import torch

    if torch.cuda.is_available():
        print(f"\n[GPU] CUDA disponível — dispositivo: {torch.cuda.get_device_name(0)}")
    else:
        print("\n[GPU] CUDA NÃO disponível — rodando em modo CPU (ponto de pareamento técnico).")

    # Asserção sempre verdadeira: a ausência de GPU é aviso, não falha de smoke.
    assert isinstance(torch.cuda.is_available(), bool)


def test_parquet_round_trip(tmp_path) -> None:
    """(c) Escrever e reler um Parquet preserva o conteúdo (contrato entre fases)."""
    df_original = pd.DataFrame({"doc_id": ["a1", "b2"], "valor": [1, 2]})
    caminho = tmp_path / "smoke.parquet"

    df_original.to_parquet(caminho)
    df_lido = pd.read_parquet(caminho)

    pd.testing.assert_frame_equal(df_original, df_lido)


def test_config_central_carrega() -> None:
    """(bônus) `config/config.yaml` carrega e valida via pydantic (AC5)."""
    from src.common.config import load_config

    config = load_config()
    assert config.fontes, "Lista de fontes não pode ser vazia."
    assert config.trend_score.w > 0
    assert config.embedding_model
