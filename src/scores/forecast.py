"""
Story 3.3: Previsão LSTM e score de surpresa Camada 2.

Método (ver ADR-001 e NFR6 — baseline obrigatório):
  1. Hold-out: os últimos `h` pontos da série ficam fora do treino.
  2. Baseline de persistência (pred = valor do dia anterior) avaliado com
     MAE/RMSE no hold-out.
  3. LSTM univariada treinada só no treino; previsão one-step-ahead no
     hold-out (usando histórico real), avaliada com MAE/RMSE.
  4. surprise_z = (real − pred_lstm) / σ_resid no último ponto, com σ dos
     resíduos do hold-out (out-of-sample); alerta quando surprise_z > k.
  5. Degradação graciosa: qualquer falha devolve os scores originais.

Reprodutibilidade: seed fixada via `config.trend_score.seed`; hiperparâmetros
da LSTM vêm da config (sem número mágico no código).
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
        if end_ix > len(serie) - 1:
            break
        seq_x, seq_y = serie[i:end_ix], serie[end_ix]
        X.append(seq_x)
        y.append(seq_y)
    return np.array(X), np.array(y)


def _treinar_lstm(train_norm: np.ndarray, n_steps: int, params: TrendScoreParams) -> LSTMModel | None:
    """Treina a LSTM nas sequências do treino normalizado; None se dados insuficientes."""
    X, y = preparar_sequencias(train_norm, n_steps)
    if len(X) < 1:
        return None

    X_tensor = torch.FloatTensor(X).view(-1, n_steps, 1)
    y_tensor = torch.FloatTensor(y).view(-1, 1)

    model = LSTMModel(hidden_size=params.lstm_hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=params.lstm_lr)
    criterion = nn.MSELoss()

    model.train()
    for _ in range(params.lstm_epochs):
        optimizer.zero_grad()
        loss = criterion(model(X_tensor), y_tensor)
        loss.backward()
        optimizer.step()

    model.eval()
    return model


def _prever_holdout(
    model: LSTMModel, counts: np.ndarray, h: int, n_steps: int,
    c_min: float, c_max: float, eps: float
) -> np.ndarray:
    """Previsões one-step-ahead da LSTM para os `h` pontos do hold-out.

    Cada previsão usa o histórico REAL até o ponto anterior (sem vazamento do
    ponto previsto), normalizado com o min/max do treino.
    """
    preds = []
    with torch.no_grad():
        for i in range(h):
            fim_hist = len(counts) - h + i  # histórico disponível até o ponto anterior
            janela = counts[fim_hist - n_steps:fim_hist]
            janela_norm = (janela - c_min) / (c_max - c_min + eps)
            entrada = torch.FloatTensor(janela_norm).view(1, n_steps, 1)
            pred_norm = model(entrada).item()
            preds.append(pred_norm * (c_max - c_min) + c_min)
    return np.array(preds)


def calcular_surpresa_l2(
    series_df: pd.DataFrame, scores_df: pd.DataFrame, params: TrendScoreParams
) -> tuple[pd.DataFrame, list[dict]]:
    """Executa a Camada 2: Baseline + LSTM + Surpresa (com avaliação em hold-out)."""
    logger.info("Iniciando Camada 2 (LSTM + Surpresa)...")

    try:
        # Reprodutibilidade (AC da Story 3.3): seed fixa da config
        torch.manual_seed(params.seed)
        np.random.seed(params.seed)

        w = params.w
        k_threshold = params.k
        eps = 1e-6
        n_steps = w

        updated_scores = scores_df.copy()
        alerts = []
        ignorados = 0

        # Inicializa colunas L2 com tipos corretos
        for col in ("pred_baseline", "pred_lstm", "surprise_z",
                    "mae_baseline", "rmse_baseline", "mae_lstm", "rmse_lstm"):
            updated_scores[col] = np.nan
        updated_scores["is_anomaly"] = pd.Series([False] * len(updated_scores), dtype=bool)

        topics = series_df["topic_id"].unique()
        for topic_id in topics:
            group = series_df[series_df["topic_id"] == topic_id].sort_values("data")
            counts = group["count"].values.astype(float)

            # Hold-out: até `w` pontos, mantendo treino suficiente p/ sequências
            h = min(w, len(counts) - (n_steps + 2))
            if h < 1:
                ignorados += 1
                continue

            train = counts[:-h]
            holdout_real = counts[-h:]

            # --- Baseline de persistência (AC1): pred[i] = valor real anterior
            holdout_baseline = counts[-h - 1:-1]
            mae_base = mean_absolute_error(holdout_real, holdout_baseline)
            rmse_base = float(np.sqrt(mean_squared_error(holdout_real, holdout_baseline)))

            # --- LSTM (AC2): treina no treino, prevê o hold-out one-step-ahead
            c_min, c_max = train.min(), train.max()
            train_norm = (train - c_min) / (c_max - c_min + eps)
            model = _treinar_lstm(train_norm, n_steps, params)
            if model is None:
                ignorados += 1
                continue

            holdout_lstm = _prever_holdout(model, counts, h, n_steps, c_min, c_max, eps)
            mae_lstm = mean_absolute_error(holdout_real, holdout_lstm)
            rmse_lstm = float(np.sqrt(mean_squared_error(holdout_real, holdout_lstm)))

            # --- Surpresa (AC3): z do último ponto com σ dos resíduos out-of-sample
            residuos = holdout_real - holdout_lstm
            sigma_resid = float(np.std(residuos))
            real_val = counts[-1]
            pred_lstm_final = holdout_lstm[-1]
            pred_baseline_final = holdout_baseline[-1]
            surprise_z = (real_val - pred_lstm_final) / (sigma_resid + eps)
            is_anomaly = bool(surprise_z > k_threshold)

            mask = updated_scores["topic_id"] == topic_id
            updated_scores.loc[mask, [
                "pred_baseline", "pred_lstm", "surprise_z",
                "mae_baseline", "rmse_baseline", "mae_lstm", "rmse_lstm"
            ]] = [
                pred_baseline_final, pred_lstm_final, surprise_z,
                mae_base, rmse_base, mae_lstm, rmse_lstm
            ]
            updated_scores.loc[mask, "is_anomaly"] = is_anomaly

            if is_anomaly:
                alerts.append({
                    "topic_id": int(topic_id),
                    "surprise_z": float(surprise_z),
                    "real": float(real_val),
                    "pred": float(pred_lstm_final),
                })

        # AC4: documenta as limitações (séries curtas ignoradas)
        if ignorados:
            logger.warning(
                "Camada 2: %d tópicos ignorados por série curta (< %d pontos).",
                ignorados, n_steps + 3,
            )

        return updated_scores, alerts
    except Exception as e:
        logger.error(f"Erro na Camada 2 (degradação graciosa p/ Camada 1): {e}")
        return scores_df, []


def salvar_alertas(alerts: list[dict], caminho: str | Path = "dados/scores/alerts.json"):
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(alerts, f, indent=2, ensure_ascii=False)
