"""
Preparação da série temporal para a aba "📈 Série Temporal" do dashboard SONAR
(Story 6.2 — camada de exibição, sem I/O e sem tocar o pipeline de scores).

Função pura e determinística: recebe a série já filtrada por tópico
(`series.parquet` — {topic_id, data, count, count_weekly}), converte `data`
para datetime e recorta o "período morto" inicial (sem nenhuma atividade
semanal), para o gráfico não ficar dominado por meses/anos achatados em zero.

Motivação (medido contra dados/scores/series.parquet, tópico 139 "lua cheia"):
a coluna `data` vem como string (Plotly a trata como eixo categórico com ~1.937
categorias) e a contagem diária (`count`) é quase sempre zero — o sinal real
está em `count_weekly`. Ver Story 6.2 (AC8-AC12).
"""

import pandas as pd

COLUNA_ATIVIDADE = "count_weekly"


def preparar_serie(df: pd.DataFrame, margem_dias: int = 7) -> pd.DataFrame:
    """
    Prepara a série de um tópico para plotagem temporal.

    - Converte a coluna `data` para `datetime64` (`pd.to_datetime`).
    - Recorta o período a partir da primeira data com `count_weekly > 0`,
      subtraindo `margem_dias` para dar uma pequena folga antes do início da
      atividade.
    - Se não houver nenhuma linha com atividade (`count_weekly` todo zero) ou
      se `df` já vier vazio, retorna um DataFrame vazio (sem exceção), para o
      chamador cair no fallback `st.info`.

    Não muta o `df` de entrada (opera sobre cópia). Determinística.

    Args:
        df: série já filtrada por tópico, com colunas {topic_id, data, count,
            count_weekly} (as demais colunas presentes são preservadas).
        margem_dias: folga (em dias) antes da primeira data com atividade.

    Returns:
        DataFrame no mesmo formato do de entrada, com `data` convertida e
        recortada — ou DataFrame vazio (mesmas colunas) se não houver atividade.
    """
    if df.empty:
        return df.copy()

    resultado = df.copy()
    resultado["data"] = pd.to_datetime(resultado["data"])

    ativos = resultado[resultado[COLUNA_ATIVIDADE] > 0]
    if ativos.empty:
        return resultado.iloc[0:0]

    corte = ativos["data"].min() - pd.Timedelta(days=margem_dias)
    return resultado[resultado["data"] >= corte].reset_index(drop=True)
