"""Helpers de leitura/escrita dos artefatos tabulares do pipeline (Parquet).

Coding Standards do projeto: **toda** persistência de dados entre fases passa
por aqui. Centralizar o IO num único módulo garante o mesmo formato (Parquet),
cria os diretórios de destino automaticamente e documenta o "contrato" de
arquivos trocados entre as stories (ex.: 1.2 escreve `urls.parquet`, 1.3 lê).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Manifesto transversal de reprodutibilidade (ver docs/architecture.md — A1).
DEFAULT_MANIFEST_PATH = Path("dados/run_manifest.json")


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


def atualizar_manifest(
    stage: str,
    *,
    n_docs: int | None = None,
    stage_version: str | None = None,
    params: dict[str, Any] | None = None,
    extras: dict[str, Any] | None = None,
    caminho: str | Path = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Atualiza (read-merge-write) o ``run_manifest.json`` transversal do pipeline.

    O manifesto é o carimbo de reprodutibilidade compartilhado por **todos** os
    estágios (ver `docs/architecture.md`). Cada estágio acrescenta sua parte sem
    sobrescrever o que os outros gravaram. Schema:
    ``{run_id, timestamp, config_hash, model_name, n_docs, n_topics,
    stage_versions, params}``.

    Args:
        stage: nome do estágio (ex.: ``"coleta"``).
        n_docs: nº de documentos produzidos (atualiza o campo top-level).
        stage_version: versão/identificador do estágio → ``stage_versions[stage]``.
        params: parâmetros a mesclar em ``params``.
        extras: outros campos top-level a sobrescrever (ex.: ``config_hash``).
        caminho: caminho do manifesto.

    Returns:
        O dicionário do manifesto atualizado.
    """
    destino = Path(caminho)
    if destino.exists():
        manifest: dict[str, Any] = json.loads(destino.read_text(encoding="utf-8"))
    else:
        manifest = {
            "run_id": None,
            "timestamp": None,
            "config_hash": None,
            "model_name": None,
            "n_docs": None,
            "n_topics": None,
            "stage_versions": {},
            "params": {},
        }

    agora = datetime.now(UTC).isoformat()
    if manifest.get("run_id") is None:
        manifest["run_id"] = agora  # o primeiro estágio a gravar fixa o run_id
    manifest["timestamp"] = agora

    if n_docs is not None:
        manifest["n_docs"] = n_docs
    if stage_version is not None:
        manifest.setdefault("stage_versions", {})[stage] = stage_version
    if params:
        manifest.setdefault("params", {}).update(params)
    if extras:
        manifest.update(extras)

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    return manifest
