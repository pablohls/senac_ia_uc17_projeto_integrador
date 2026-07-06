"""
Story 3.4: Validação por Backtest.

Simula o sistema "congelado no tempo": para cada data de corte T, recalcula os
scores usando SOMENTE dados até T (sem vazamento de futuro) e observa como o
trend_score do tópico evolui conforme T avança sobre um surto real.

Uso:
  poetry run python -m src.scores.backtest                     # tópico automático
  poetry run python -m src.scores.backtest --topic 12          # tópico específico
  poetry run python -m src.scores.backtest --datas 2026-06-20 2026-06-27 2026-07-04
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.common.config import load_config
from src.scores.trend_score import trend_score_l1
from src.scores.forecast import calcular_surpresa_l2

logger = logging.getLogger(__name__)

SERIES_PATH = "dados/scores/series.parquet"
RELATORIO_PATH = "docs/qa/validacao_backtest.md"


def escolher_topico_automatico(df_series: pd.DataFrame, config) -> int:
    """Escolhe o tópico com maior surto recente (candidato natural do backtest).

    Critério: maior trend_score L1 na data final da série, excluindo outliers
    (topic_id = -1). É o tópico cuja história o backtest deve reconstruir.
    """
    scores = trend_score_l1(df_series[df_series["topic_id"] != -1], config.trend_score)
    scores_validos = scores[scores["support_ok"]]
    if scores_validos.empty:
        raise ValueError(
            "Nenhum tópico com suporte mínimo para o backtest "
            f"(n_min={config.trend_score.n_min}). Corpus insuficiente."
        )
    return int(scores_validos.iloc[0]["topic_id"])


def gerar_datas_corte(df_series: pd.DataFrame, n_cortes: int, passo_dias: int) -> list[pd.Timestamp]:
    """Gera cortes retroativos a partir da última data da série (T-3p, T-2p, T-p, T)."""
    data_max = pd.to_datetime(df_series["data"]).max()
    return [data_max - pd.Timedelta(days=passo_dias * i) for i in range(n_cortes - 1, -1, -1)]


def executar_backtest(series_path: str, datas_corte: list, topic_id: int) -> pd.DataFrame:
    """Recalcula L1+L2 em cada corte T usando apenas dados <= T (sem leakage)."""
    config = load_config()
    df_series = pd.read_parquet(series_path)
    df_series["data"] = pd.to_datetime(df_series["data"])

    resultados = []
    for data_corte in datas_corte:
        T = pd.to_datetime(data_corte)
        series_t = df_series[df_series["data"] <= T].copy()
        if series_t.empty:
            logger.warning("Corte %s anterior ao início da série — ignorado.", T.date())
            continue

        scores_l1 = trend_score_l1(series_t, config.trend_score, t_ref=T)
        # L2 só para o tópico-alvo (treinar LSTM dos ~150 tópicos por corte
        # custaria minutos sem mudar o resultado do relatório)
        serie_alvo = series_t[series_t["topic_id"] == topic_id]
        scores_alvo = scores_l1[scores_l1["topic_id"] == topic_id]
        scores_l2, _ = calcular_surpresa_l2(serie_alvo, scores_alvo, config.trend_score)

        row = scores_l2[scores_l2["topic_id"] == topic_id]
        if not row.empty:
            res = row.iloc[0].to_dict()
            res["T_simulado"] = T.date()
            resultados.append(res)

    return pd.DataFrame(resultados)


def _analise_qualitativa(df_res: pd.DataFrame) -> str:
    """Gera a análise a partir dos números reais — relato honesto (AC3)."""
    if len(df_res) < 2:
        return (
            "Não há cortes suficientes para avaliar a evolução do score. "
            "Backtest inconclusivo — repetir com uma janela maior de dados.\n"
        )

    scores = df_res["trend_score"].tolist()
    subiu = scores[-1] > scores[0]
    anomalias = df_res["is_anomaly"].fillna(False).astype(bool).sum()

    linhas = []
    if subiu:
        linhas.append(
            f"O trend_score do tópico subiu de {scores[0]:.2f} (corte inicial) para "
            f"{scores[-1]:.2f} (corte final), indicando que o sistema teria sinalizado "
            "a ascensão do assunto conforme os dados chegavam."
        )
    else:
        linhas.append(
            f"O trend_score do tópico NÃO subiu entre os cortes ({scores[0]:.2f} → "
            f"{scores[-1]:.2f}). Neste período o sistema não caracterizaria o assunto "
            "como tendência em ascensão — resultado registrado de forma honesta."
        )

    if anomalias > 0:
        linhas.append(
            f"A Camada 2 (LSTM) marcou anomalia em {anomalias} de {len(df_res)} cortes "
            "(surpresa acima de k desvios-padrão)."
        )
    else:
        linhas.append(
            "A Camada 2 (LSTM) não marcou anomalias nos cortes avaliados."
        )

    linhas.append(
        "Limitações: janela histórica curta em relação ao horizonte H do ADR-001; "
        "cortes simulados com dados congelados (nenhum vazamento de futuro — o corte "
        "`data <= T` é aplicado antes de qualquer cálculo)."
    )
    return "\n\n".join(linhas) + "\n"


def gerar_relatorio_backtest(
    df_res: pd.DataFrame, topic_id: int, output_path: str = RELATORIO_PATH
) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    colunas = [
        c for c in ["T_simulado", "R", "growth", "trend_score", "surprise_z", "is_anomaly"]
        if c in df_res.columns
    ]
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Relatório de Validação por Backtest (Story 3.4)\n\n")
        f.write(f"**Tópico analisado:** {topic_id}\n\n")
        f.write("**Metodologia:** para cada data de corte T, os scores foram recalculados "
                "usando somente dados com `data <= T` (simulação sem vazamento de futuro).\n\n")
        f.write("## 1. Resultados quantitativos\n\n")
        if df_res.empty:
            f.write("_Sem resultados — tópico ausente nos cortes avaliados._\n\n")
        else:
            # Tabela markdown sem depender do `tabulate` (dependência opcional
            # do pandas.to_markdown que não está no projeto)
            df_fmt = df_res[colunas].copy()
            for c in df_fmt.select_dtypes("float").columns:
                df_fmt[c] = df_fmt[c].map(lambda v: f"{v:.3f}")
            f.write("| " + " | ".join(colunas) + " |\n")
            f.write("|" + "---|" * len(colunas) + "\n")
            for _, linha in df_fmt.iterrows():
                f.write("| " + " | ".join(str(v) for v in linha.values) + " |\n")
            f.write("\n")
        f.write("## 2. Análise qualitativa\n\n")
        f.write(_analise_qualitativa(df_res))
    logger.info("Relatório salvo em %s", output_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest do Trend Score (Story 3.4)")
    parser.add_argument("--series", default=SERIES_PATH, help="Caminho do series.parquet")
    parser.add_argument("--topic", type=int, default=None,
                        help="topic_id a avaliar (default: maior score atual)")
    parser.add_argument("--datas", nargs="*", default=None,
                        help="Datas de corte YYYY-MM-DD (default: 4 cortes semanais retroativos)")
    parser.add_argument("--saida", default=RELATORIO_PATH, help="Caminho do relatório .md")
    args = parser.parse_args()

    config = load_config()
    df_series = pd.read_parquet(args.series)
    df_series["data"] = pd.to_datetime(df_series["data"])

    topic_id = args.topic if args.topic is not None else escolher_topico_automatico(df_series, config)
    datas = args.datas if args.datas else gerar_datas_corte(df_series, n_cortes=4, passo_dias=7)

    logger.info("Backtest do tópico %d com cortes: %s", topic_id,
                [str(pd.to_datetime(d).date()) for d in datas])

    df_backtest = executar_backtest(args.series, datas, topic_id=topic_id)
    gerar_relatorio_backtest(df_backtest, topic_id=topic_id, output_path=args.saida)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    main()
