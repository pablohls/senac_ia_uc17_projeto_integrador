# Relatório de Validação por Backtest (Story 3.4)

**Tópico analisado:** 0

**Metodologia:** para cada data de corte T, os scores foram recalculados usando somente dados com `data <= T` (simulação sem vazamento de futuro).

## 1. Resultados quantitativos

| T_simulado | R | growth | trend_score | surprise_z | is_anomaly |
|---|---|---|---|---|---|
| 2026-06-15 | 20 | 1.750 | 1.865 | 0.503 | False |
| 2026-06-22 | 7 | 0.381 | -2.007 | -0.601 | False |
| 2026-06-29 | 5 | 0.750 | -0.515 | 0.486 | False |
| 2026-07-06 | 16 | 2.833 | 3.348 | -0.285 | False |

## 2. Análise qualitativa

O trend_score do tópico subiu de 1.86 (corte inicial) para 3.35 (corte final), indicando que o sistema teria sinalizado a ascensão do assunto conforme os dados chegavam.

A Camada 2 (LSTM) não marcou anomalias nos cortes avaliados.

Limitações: janela histórica curta em relação ao horizonte H do ADR-001; cortes simulados com dados congelados (nenhum vazamento de futuro — o corte `data <= T` é aplicado antes de qualquer cálculo).
