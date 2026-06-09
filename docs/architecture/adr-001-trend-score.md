# ADR-001 — Trend Score de 2 camadas

- **Status:** Aceito
- **Data:** 2026-06-09
- **Decisores:** @analyst (Atlas, origem na sessão de brainstorming) · @architect (Aria, registro)
- **Fonte:** `docs/design/trend-score.md`
- **Relacionado:** `docs/prd.md` (FR7 MUST, FR8 SHOULD, FR9), `docs/architecture.md`

---

## Contexto

O produto precisa de uma definição **concreta e defensável** de "tendência emergente". Dois problemas tornam isso não-trivial:

1. **Crescimento puro engana:** clusters minúsculos com 1→3 menções têm crescimento de 300% mas não são tendência real — ruído infla o ranking.
2. **Tensão DL vs. séries curtas:** o curso exige Deep Learning, mas o corpus cobre poucos meses → séries temporais curtas, terreno arriscado para uma LSTM sozinha sustentar o produto.

## Decisão

Adotar uma **arquitetura de 2 camadas complementares**:

### Camada 1 — Trend Score estatístico (MUST)

```
TrendScore_i = volume_i · log(growth_i) + λ · max(0, z_i)
```

- `volume_i = log(1 + R_i)` — volume amortecido (anti-ruído de clusters pequenos).
- `growth_i = (R_i + α) / (P_i + α)` — crescimento recente vs. janela anterior, com suavização de Laplace (`α=1`).
- `z_i = (R_i/w − μ_i) / (σ_i + ε)` — burst vs. própria história (janela `H=60d`).
- `λ=1.0` pondera o burst; `log(growth)` é positivo ao crescer / negativo ao encolher (penaliza queda sem `if`); `max(0, z)` só premia surtos.
- **Guardas:** suporte mínimo `n_min=5`; tópico novo (`P=0`) ganha badge "novo" em vez de score inflado.

**Ranqueia os "Tópicos em Ascensão". Funciona sem ML — é o plano B garantido.**

### Camada 2 — Surpresa de previsão (SHOULD)

```
surprise_z_i(T) = (real_i(T) − pred_i(T)) / (σ_resid_i + ε)
```

- **LSTM univariada** prevê a frequência futura do tópico; alerta de "sinal forte/anomalia" quando `surprise_z > k` (`k=2.5`).
- **Baseline obrigatório** (persistência / média móvel / seasonal-naive) sempre avaliado junto, com **MAE/RMSE em hold-out** — comparação honesta (NFR6).

## Consequências

**Positivas**
- ✅ **Plano B garantido:** se a LSTM não performa, a Camada 1 sustenta o produto e a banca vê rigor estatístico.
- ✅ **DL com propósito de produto:** a LSTM vira "detector de surpresa", não experimento solto → resolve a tensão DL-vs-séries-curtas.
- ✅ **Narrativa de banca forte:** mostrar onde as 2 camadas **concordam** (alta confiança) e **discordam** (discussão rica).
- ✅ **Degradação graciosa codificável:** `scores.parquet` evolutivo (L1 base, L2 acrescenta colunas) + `alerts.json` opcional permitem o dashboard funcionar só com L1.

**Negativas / custos**
- ⚠️ Manter duas lógicas + parametrização (`w, α, H, λ, n_min, k, ε`). **Mitigação:** centralizar em `config.yaml` validado por pydantic.
- ⚠️ Camada 2 depende de GPU e de séries suficientemente longas. **Mitigação:** best-effort isolada; falha não quebra o pipeline.

## Alternativas rejeitadas

| Alternativa | Por que rejeitada |
|---|---|
| Fórmula única de crescimento | Frágil a ruído de clusters pequenos; sem robustez estatística. |
| Só LSTM | Arriscado com séries curtas; sem plano B se não performar. |
| Detecção de anomalia clássica (STL/ESD) sem DL | Perderia o requisito de Deep Learning do curso. |

## Parâmetros (defaults tunáveis)

| Parâmetro | Default | Papel |
|---|---|---|
| `w` (janela) | 7 dias | recente vs. anterior |
| `α` (suavização) | 1 | evita div/0, tempera novos |
| `H` (histórico burst) | 60 dias | base de μ,σ |
| `λ` (peso burst) | 1.0 | importância do z-score |
| `n_min` (suporte) | 5 | corte de ruído |
| `k` (limiar surpresa) | 2.5 | gatilho de alerta |
| `ε` | 1e-6 | estabilidade numérica |

> Qualquer ajuste destes defaults deve ser documentado no relatório final com o **porquê** — a banca valoriza tuning justificado.

## Implementação

- **Camada 1** em `src/scores/trend_score.py` (determinística → **alvo dos testes unitários**).
- **Camada 2** em `src/scores/forecast.py` (estocástica/GPU → validação por métricas, best-effort).
- Validação por **backtest** (Story 3.4): fixar `T` antes de um surto conhecido e verificar que `trend_score`/`surprise_z` sobem depois.
