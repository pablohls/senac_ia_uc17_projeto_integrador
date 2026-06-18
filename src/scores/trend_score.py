"""
Story 3.2: Trend Score Camada 1 (estatístico).
"""

from __future__ import annotations
from datetime import datetime
import numpy as np
import pandas as pd
from src.common.config import TrendScoreParams

def trend_score_l1(series: pd.DataFrame, params: TrendScoreParams, t_ref: datetime | None = None) -> pd.DataFrame:
    """Calcula o Trend Score Camada 1 para cada tópico."""
    df = series.copy()
    df["data"] = pd.to_datetime(df["data"])
    
    T = pd.to_datetime(t_ref) if t_ref is not None else df["data"].max()
    w = params.w
    alpha = params.alpha
    H = params.H
    lam = params.lambda_burst
    n_min = params.n_min
    eps = 1e-6

    # Datas das janelas
    recente_inicio = T - pd.Timedelta(days=w-1)
    anterior_inicio = T - pd.Timedelta(days=2*w-1)
    anterior_fim = T - pd.Timedelta(days=w)
    hist_inicio = T - pd.Timedelta(days=H+w-1)
    hist_fim = T - pd.Timedelta(days=w)

    results = []
    for topic_id, group in df.groupby("topic_id"):
        # R: [T-w+1, T]
        R = group.loc[(group["data"] >= recente_inicio) & (group["data"] <= T), "count"].sum()
        
        # P: [T-2w+1, T-w]
        P = group.loc[(group["data"] >= anterior_inicio) & (group["data"] <= anterior_fim), "count"].sum()
        
        # Histórico H: [T-H-w+1, T-w]
        hist_values = group.loc[(group["data"] >= hist_inicio) & (group["data"] <= hist_fim), "count"].values
        
        # Cálculos
        growth = (R + alpha) / (P + alpha)
        volume = np.log1p(R)
        
        if len(hist_values) > 0:
            mu = np.mean(hist_values)
            sigma = np.std(hist_values)
            if sigma < eps:
                z = 1.0 if (R/w) > mu else 0.0
            else:
                z = ((R / w) - mu) / (sigma + eps)
        else:
            z = 0.0
            
        trend_score = volume * np.log(growth) + lam * max(0, z)
        
        # Badges
        primeira_aparicao = group.loc[group["count"] > 0, "data"].min()
        idade_dias = (T - primeira_aparicao).days if pd.notnull(primeira_aparicao) else 0
        is_new = (P == 0) and (idade_dias < w)
        support_ok = R >= n_min
        
        results.append({
            "topic_id": topic_id, "T": T, "R": R, "P": P,
            "growth": growth, "volume": volume, "z": z,
            "trend_score": trend_score if support_ok else -np.inf,
            "is_new": is_new, "support_ok": support_ok
        })
        
    res_df = pd.DataFrame(results)
    res_df["rank"] = res_df.loc[res_df["support_ok"], "trend_score"].rank(ascending=False, method="min")
    return res_df.sort_values("trend_score", ascending=False)
