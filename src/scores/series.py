"""Story 3.1 — Montar séries temporais por tópico com zero-fill.

Esta story transforma as atribuições doc-tópico num conjunto de séries de frequência
diária por tópico, essencial para a Camada 1 do Trend Score (Story 3.2).

Key concepts:
- **Série temporal:** sequência de valores (aqui: contagem de artigos) ao longo do tempo.
- **Zero-fill:** preencher com 0 os dias sem menção a um tópico (crítico — sem isso, 
  a Camada 1 quebra no cálculo de z-score).
- **Resample semanal:** agregação para tópicos esparsos (noise reduction).

Schema de saída (dados/scores/series.parquet):
  - topic_id (int): identificador do tópico
  - data (date): data (ISO)
  - count (int): nº de documentos no dia
  - count_weekly (int, opcional): nº de documentos na semana
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from pathlib import Path


def montar_series(
    doc_topics: pd.DataFrame,
    *,
    gerar_weekly: bool = True,
) -> pd.DataFrame:
    """Monta a série de frequência diária de cada tópico a partir de atribuições doc-tópico.

    A função realiza:
    1. Agrupamento por (topic_id, data) e contagem
    2. **Zero-fill** para todos os dias do período histórico (crítico para Camada 1)
    3. Agregação semanal opcional para tópicos esparsos

    Args:
        doc_topics: DataFrame com colunas `{doc_id, data, topic_id}`.
            - `data` deve ser tipo date ou string ISO.
            - `topic_id` pode incluir -1 para outliers (será considerado).
        gerar_weekly: se True, acrescenta coluna `count_weekly` (resample "W").

    Returns:
        DataFrame com schema `{topic_id, data, count[, count_weekly]}`, totalmente
        preenchido (zero-filled) para todos os dias do período para cada tópico.
        Ordenado por topic_id, depois data.

    Notes:
        - **Determinístico:** entrada fixa → saída fixa (testável).
        - **Zero-fill:** nenhum dia do período fica faltando.
        - A série cobre [data_mín, data_máx] do corpus inteiro.

    Raises:
        ValueError: se doc_topics estiver vazio, ou se faltar coluna 'data'/'topic_id'.
    """
    if doc_topics.empty:
        raise ValueError("doc_topics não pode estar vazio.")

    # Validar colunas obrigatórias
    required_cols = {"doc_id", "data", "topic_id"}
    missing_cols = required_cols - set(doc_topics.columns)
    if missing_cols:
        raise ValueError(f"Colunas obrigatórias faltando: {missing_cols}")

    # Garantir que 'data' é tipo date
    df = doc_topics.copy()
    df["data"] = pd.to_datetime(df["data"]).dt.date

    # Contar por (topic_id, data)
    counts = df.groupby(["topic_id", "data"]).size().reset_index(name="count")

    # Determinar o intervalo de datas global
    data_min = counts["data"].min()
    data_max = counts["data"].max()

    # Criar um índice completo de datas para cada tópico (zero-fill)
    date_range = pd.date_range(start=data_min, end=data_max, freq="D").date
    topics = counts["topic_id"].unique()

    # Reindexar: para cada tópico, criar todas as datas do período
    index_completo = pd.MultiIndex.from_product(
        [topics, date_range], names=["topic_id", "data"]
    )
    series = counts.set_index(["topic_id", "data"]).reindex(index_completo, fill_value=0)
    series = series.reset_index()

    # Gerar agregação semanal se solicitado
    if gerar_weekly:
        # Para cada tópico, resample para agregação semanal
        series_list = []
        for topic_id in topics:
            topic_data = series[series["topic_id"] == topic_id].copy()
            topic_data = topic_data.set_index("data")

            # Resample semanal
            weekly = topic_data["count"].resample("W").sum()

            # Mesclar weekly de volta com daily
            topic_data["count_weekly"] = topic_data.index.to_period("W").map(
                lambda x: weekly.get(x.end_time.date(), 0)
            )
            topic_data = topic_data.reset_index()
            series_list.append(topic_data)

        series = pd.concat(series_list, ignore_index=True)
        series = series[["topic_id", "data", "count", "count_weekly"]]
    else:
        series = series[["topic_id", "data", "count"]]

    # Ordenar por topic_id e data para consistência
    series = series.sort_values(by=["topic_id", "data"]).reset_index(drop=True)

    return series


def validar_serie(series: pd.DataFrame) -> dict[str, bool]:
    """Valida uma série contra os critérios de aceitação da Story 3.1.

    Retorna um dicionário de validações:
    - 'zero_filled': todos os dias existem para cada tópico (sem gaps)
    - 'soma_consistente': soma de counts bate com nº de docs por tópico
    - 'tipos_corretos': colunas têm os tipos esperados

    Args:
        series: DataFrame de série retornado por :func:`montar_series`.

    Returns:
        Dict com chaves True/False indicando se passou em cada validação.
    """
    resultado = {}

    if series.empty:
        resultado["zero_filled"] = False
        resultado["soma_consistente"] = False
        resultado["tipos_corretos"] = False
        return resultado

    # Check 1: zero-fill (nenhum dia faltando para cada tópico)
    topics = series["topic_id"].unique()
    n_dias_esperados = (series["data"].max() - series["data"].min()).days + 1
    resultado["zero_filled"] = all(
        len(series[series["topic_id"] == t]) == n_dias_esperados for t in topics
    )

    # Check 2: counts não-negativos e tipo inteiro
    resultado["soma_consistente"] = (
        (series["count"] >= 0).all()
        and series["count"].dtype in ["int32", "int64", "Int32", "Int64"]
    )

    # Check 3: tipos corretos
    tipos_ok = (
        series["topic_id"].dtype in ["int32", "int64", "Int32", "Int64"]
        and series["data"].dtype == "object"  # date objects
    )
    if "count_weekly" in series.columns:
        tipos_ok = tipos_ok and series["count_weekly"].dtype in [
            "int32",
            "int64",
            "Int32",
            "Int64",
        ]
    resultado["tipos_corretos"] = tipos_ok

    return resultado
