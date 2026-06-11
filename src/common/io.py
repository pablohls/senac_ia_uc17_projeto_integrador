"""Helpers de leitura/escrita dos artefatos tabulares do pipeline (Parquet).

Coding Standards do projeto: **toda** persistência de dados entre fases passa
por aqui. Centralizar o IO num único módulo garante o mesmo formato (Parquet),
cria os diretórios de destino automaticamente e documenta o "contrato" de
arquivos trocados entre as stories (ex.: 1.2 escreve `urls.parquet`, 1.3 lê).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


def salvar_parquet(df: pd.DataFrame, caminho: str | Path) -> Path:
    """Grava um DataFrame em Parquet, criando os diretórios necessários.

    Args:
        df: DataFrame a persistir.
        caminho: destino (ex.: ``dados/raw/urls.parquet``).

    Returns:
        O :class:`~pathlib.Path` absoluto do arquivo gravado.
    """
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    return destino.resolve()


def ler_parquet(caminho: str | Path) -> pd.DataFrame:
    """Lê um Parquet em DataFrame.

    Args:
        caminho: arquivo de origem.

    Returns:
        O DataFrame lido.

    Raises:
        FileNotFoundError: se o arquivo não existir.
    """
    origem = Path(caminho)
    if not origem.exists():
        raise FileNotFoundError(f"Arquivo Parquet não encontrado: {origem}")
    return pd.read_parquet(origem)
