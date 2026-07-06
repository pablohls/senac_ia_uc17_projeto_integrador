# Relatório de Validação por Backtest (Story 3.4)

**Tópico analisado:** 139

**Metodologia:** para cada data de corte T, os scores foram recalculados usando somente dados com `data <= T` (simulação sem vazamento de futuro).

## 1. Resultados quantitativos

| T_simulado | R | growth | trend_score | surprise_z | is_anomaly |
|---|---|---|---|---|---|
| 2026-06-15 | 0 | 1.000 | -inf | 0.000 | False |
| 2026-06-22 | 0 | 1.000 | -inf | 0.000 | False |
| 2026-06-29 | 0 | 1.000 | -inf | 0.000 | False |
| 2026-07-06 | 7 | 8.000 | 8.066 | 0.700 | False |

## 2. Análise qualitativa

O trend_score do tópico subiu de -inf (corte inicial) para 8.07 (corte final), indicando que o sistema teria sinalizado a ascensão do assunto conforme os dados chegavam.

A Camada 2 (LSTM) não marcou anomalias nos cortes avaliados.

Limitações: janela histórica curta em relação ao horizonte H do ADR-001; cortes simulados com dados congelados (nenhum vazamento de futuro — o corte `data <= T` é aplicado antes de qualquer cálculo).
