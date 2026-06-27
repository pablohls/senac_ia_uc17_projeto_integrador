from __future__ import annotations

import pandas as pd

def montar_series(doc_topics: pd.DataFrame, *, gerar_weekly: bool = True) -> pd.DataFrame:
    if doc_topics.empty:
        raise ValueError("doc_topics não pode estar vazio.")

    required_cols = {"doc_id", "data", "topic_id"}
    missing_cols = required_cols - set(doc_topics.columns)
    if missing_cols:
        raise ValueError(f"Colunas obrigatórias faltando: {missing_cols}")

    df = doc_topics.copy()
    df["data"] = pd.to_datetime(df["data"])

    # 1. Contar documentos por dia e tópico
    counts = df.groupby([df["data"].dt.date, "topic_id"]).size().reset_index(name="count")
    counts.columns = ["data", "topic_id", "count"]
    counts["data"] = pd.to_datetime(counts["data"])

    # 2. Criar todas as combinações de data e tópico (zero-fill)
    data_min = counts["data"].min()
    data_max = counts["data"].max()
    date_range = pd.date_range(start=data_min, end=data_max, freq="D")
    topics = counts["topic_id"].unique()

    df_completo = pd.DataFrame()
    for topic in topics:
        df_topic = pd.DataFrame({"data": date_range, "topic_id": topic})
        df_completo = pd.concat([df_completo, df_topic])

    # 3. Juntar e preencher zeros
    series = df_completo.merge(counts, on=["data", "topic_id"], how="left")
    series["count"] = series["count"].fillna(0).astype(int)

    # 4. Agregação semanal (se solicitado)
    if gerar_weekly:
        # Usar a abordagem manual: calcular a semana a partir da data
        # A semana 0 começa no primeiro domingo do ano
        series["dias_desde_inicio"] = (series["data"] - pd.Timestamp(data_min)).dt.days
        series["semana"] = series["dias_desde_inicio"] // 7
        
        # Calcular total semanal por tópico
        weekly = series.groupby(["semana", "topic_id"])["count"].sum().reset_index()
        weekly.columns = ["semana", "topic_id", "count_weekly"]
        
        # Juntar com os dados diários
        series = series.merge(weekly, on=["semana", "topic_id"], how="left")
        series["count_weekly"] = series["count_weekly"].fillna(0).astype(int)
        
        # Remover colunas auxiliares
        series = series.drop(["semana", "dias_desde_inicio"], axis=1)
        series = series[["topic_id", "data", "count", "count_weekly"]]
    else:
        series = series[["topic_id", "data", "count"]]

    # 5. Converter data para date
    series["data"] = series["data"].dt.date

    # 6. Ordenar
    series = series.sort_values(by=["topic_id", "data"]).reset_index(drop=True)

    return series


def validar_serie(series: pd.DataFrame) -> dict[str, bool]:
    if series.empty:
        return {"zero_filled": False, "soma_consistente": False, "tipos_corretos": False}

    topics = series["topic_id"].unique()
    n_dias_esperados = (series["data"].max() - series["data"].min()).days + 1

    zero_filled = all(len(series[series["topic_id"] == t]) == n_dias_esperados for t in topics)

    soma_consistente = (
        (series["count"] >= 0).all() and
        series["count"].dtype in ["int32", "int64", "Int32", "Int64"]
    )

    tipos_ok = (
        series["topic_id"].dtype in ["int32", "int64", "Int32", "Int64"] and
        series["data"].dtype == "object"
    )

    if "count_weekly" in series.columns:
        tipos_ok = tipos_ok and series["count_weekly"].dtype in ["int32", "int64", "Int32", "Int64"]

    return {
        "zero_filled": zero_filled,
        "soma_consistente": soma_consistente,
        "tipos_corretos": tipos_ok
    }
