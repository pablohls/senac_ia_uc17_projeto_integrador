"""
Story 3.3: Previsão LSTM e score de surpresa Camada 2.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_absolute_error, mean_squared_error
from src.common.config import TrendScoreParams

logger = logging.getLogger(__name__)

class LSTMModel(nn.Module):
    """Modelo LSTM univariado simples para previsão de séries temporais."""
    def __init__(self, input_size=1, hidden_size=32, num_layers=1, output_size=1):
        super(LSTMModel, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        out, _ = self.lstm(x, (h0, c0))
        out = self.fc(out[:, -1, :])
        return out

def preparar_sequencias(serie, n_steps):
    """Prepara janelas deslizantes para treino da LSTM."""
    X, y = [], []
    for i in range(len(serie)):
        end_ix = i + n_steps
        if end_ix > len(serie)-1:
            break
        seq_x, seq_y = serie[i:end_ix], serie[end_ix]
        X.append(seq_x)
        y.append(seq_y)
    return np.array(X), np.array(y)

def calcular_surpresa_l2(series_df: pd.DataFrame, scores_df: pd.DataFrame, params: TrendScoreParams) -> tuple[pd.DataFrame, list[dict]]:
    """Executa a Camada 2: Baseline + LSTM + Surpresa."""
    logger.info("Iniciando Camada 2 (LSTM + Surpresa)...")
    
    try:
        w = params.w
        k_threshold = params.k
        eps = 1e-6
        n_steps = w
        
        updated_scores = scores_df.copy()
        alerts = []
        
        # Inicializa colunas L2 com tipos corretos
        updated_scores["pred_baseline"] = np.nan
        updated_scores["pred_lstm"] = np.nan
        updated_scores["surprise_z"] = np.nan
        updated_scores["mae_lstm"] = np.nan
        updated_scores["rmse_lstm"] = np.nan
        updated_scores["is_anomaly"] = pd.Series([False] * len(updated_scores), dtype=bool)
            
        topics = series_df["topic_id"].unique()
        for topic_id in topics:
            group = series_df[series_df["topic_id"] == topic_id].sort_values("data")
            counts = group["count"].values.astype(float)
            
            if len(counts) < (n_steps + 2):
                continue
                
            train_data = counts[:-1]
            real_val = counts[-1]
            pred_baseline = train_data[-1]
            
            # Normalização Min-Max
            c_min, c_max = train_data.min(), train_data.max()
            train_norm = (train_data - c_min) / (c_max - c_min + eps)
            
            X, y = preparar_sequencias(train_norm, n_steps)
            if len(X) < 1: continue
                
            X_tensor = torch.FloatTensor(X).view(-1, n_steps, 1)
            y_tensor = torch.FloatTensor(y).view(-1, 1)
            
            model = LSTMModel()
            optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
            criterion = nn.MSELoss()
            
            model.train()
            for epoch in range(50):
                optimizer.zero_grad(); loss = criterion(model(X_tensor), y_tensor); loss.backward(); optimizer.step()
            
            model.eval()
            with torch.no_grad():
                last_window = torch.FloatTensor(train_norm[-n_steps:]).view(1, n_steps, 1)
                pred_lstm = model(last_window).item() * (c_max - c_min) + c_min
                train_preds = model(X_tensor).numpy().flatten() * (c_max - c_min) + c_min
                y_orig = y * (c_max - c_min) + c_min
                sigma_resid = np.std(y_orig - train_preds)
            
            surprise_z = (real_val - pred_lstm) / (sigma_resid + eps)
            is_anomaly = surprise_z > k_threshold
            
            mask = updated_scores["topic_id"] == topic_id
            updated_scores.loc[mask, ["pred_baseline", "pred_lstm", "surprise_z", "is_anomaly"]] = [pred_baseline, pred_lstm, surprise_z, is_anomaly]
            
            if is_anomaly:
                alerts.append({"topic_id": int(topic_id), "surprise_z": float(surprise_z), "real": float(real_val), "pred": float(pred_lstm)})
                
        return updated_scores, alerts
    except Exception as e:
        logger.error(f"Erro na Camada 2: {e}")
        return scores_df, []

def salvar_alertas(alerts: list[dict], caminho: str | Path = "dados/scores/alerts.json"):
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, ensure_ascii=False)
