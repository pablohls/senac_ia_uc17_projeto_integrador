# Design Spec — Trend Score (SONAR)

> **Origem:** sessão de brainstorming facilitada por @analyst (Atlas), 2026-06-08
> **Objetivo da sessão:** definir uma fórmula concreta e defensável de "tendência emergente"
> **Decisão:** arquitetura de **2 camadas** (score estatístico robusto + surpresa por deep learning)
> **Consumidores:** @architect (ADR), @dev (implementação), dashboard
> **Relacionado:** `docs/brief.md`, `docs/research/2026-06-08-backfill-historico/findings.md`

---

## 1. Resumo da decisão

Em vez de uma fórmula única, o Trend Score tem **duas camadas complementares**:

- **Camada 1 — Trend Score estatístico:** ranqueia os "Tópicos em Ascensão". Robusto, sem ML, **funciona mesmo se a LSTM falhar** (plano B garantido).
- **Camada 2 — Surpresa de previsão (LSTM):** detecta tópicos que crescem **além do esperado pelo modelo** → alerta de "sinal forte/anomalia". Faz o deep learning ser o **motor do produto**, não um experimento lateral.

**Narrativa de banca:** "score estatístico robusto + detector de surpresa por deep learning; mostramos onde concordam e onde discordam."

---

## 2. Notação

- Tópico `i` (cluster do HDBSCAN/BERTopic), tempo discreto `t` em **dias**.
- `c_i(t)` = nº de artigos do tópico `i` publicados no dia `t`.
- `T` = "agora" (dia mais recente da análise).
- **Granularidade:** diária por padrão (validado: ~50–70 artigos/dia no Olhar Digital). Para tópicos esparsos, agregar por **semana** na série usada pela LSTM.

---

## 3. Camada 1 — Trend Score estatístico

### Componentes

Janela curta `w` (default **7 dias**) e janela de referência de mesmo tamanho imediatamente anterior:

```
R_i = Σ c_i(t)   para t em [T-w+1, T]        # contagem recente
P_i = Σ c_i(t)   para t em [T-2w+1, T-w]     # contagem anterior
```

- **Crescimento (com suavização de Laplace):**
  `growth_i = (R_i + α) / (P_i + α)`, com `α = 1` → evita divisão por zero e tempera tópicos novos.
- **Volume amortecido (anti-ruído):**
  `volume_i = log(1 + R_i)` → cluster minúsculo não infla o score.
- **Burst vs. própria história (z-score):**
  sobre um histórico longo `H` (default **60 dias**, excluindo a janela atual), calcule `μ_i, σ_i` da taxa diária `c_i(t)`. Então
  `z_i = (R_i / w − μ_i) / (σ_i + ε)`, com `ε = 1e-6`.

### Fórmula final (Camada 1)

```
TrendScore_i = volume_i × log(growth_i) + λ × max(0, z_i)
```

- `λ` (default **1.0**) pondera o componente de burst. `log(growth)` é **positivo quando cresce, negativo quando encolhe** → penaliza naturalmente tópicos em queda. `max(0, z_i)` só premia surtos positivos.

### Guardas (edge cases)

| Caso | Tratamento |
|------|-----------|
| Suporte mínimo | só ranqueia se `R_i ≥ n_min` (default **5**); abaixo disso → rótulo "amostra insuficiente". |
| Tópico novo (`P_i = 0`) | suavização cobre; marcar badge **"novo"** se idade do tópico `< w`, em vez de score inflado. |
| Exibição no dashboard | normalizar por rank ou min-max entre tópicos para a barra visual. |

---

## 4. Camada 2 — Surpresa de previsão (LSTM)

### Previsão

Para tópicos com série suficientemente longa:
- **Baseline (obrigatório, p/ comparação honesta):** persistência (`pred = último valor`), média móvel, ou *seasonal-naive* (mesmo dia da semana anterior).
- **Modelo DL:** **LSTM univariada** (opcionalmente com exógenas: dia da semana). Avaliar **MAE/RMSE** em cauda de teste (*hold-out*), **sempre comparando com o baseline**.

### Score de surpresa

```
surprise_i(T)   = (real_i(T) − pred_i(T)) / (pred_i(T) + ε)
surprise_z_i(T) = (real_i(T) − pred_i(T)) / (σ_resid_i + ε)
```

- `σ_resid_i` = desvio-padrão dos resíduos do modelo na validação.
- **Alerta "sinal forte/anomalia"** quando `surprise_z_i > k` (default **k = 2.5**), especialmente para tópicos novos/baixo-baseline em surto.

### Visão de concordância (diferencial de banca)

- Tópicos no **top-N de ambas** as camadas → **tendência de alta confiança**.
- **Discordâncias** (alto na Camada 1, baixo na 2, ou vice-versa) → pontos de discussão ricos na apresentação.

---

## 5. Parâmetros (defaults tunáveis)

| Parâmetro | Default | Papel |
|-----------|---------|-------|
| `w` (janela) | 7 dias | recente vs. anterior |
| `α` (suavização) | 1 | evita div/0, tempera novos |
| `H` (histórico burst) | 60 dias | base de μ,σ |
| `λ` (peso burst) | 1.0 | importância do z-score |
| `n_min` (suporte) | 5 | corte de ruído |
| `k` (limiar surpresa) | 2.5 | gatilho de alerta |
| `ε` | 1e-6 | estabilidade numérica |

> Documentar no relatório final qualquer ajuste desses defaults e o **porquê** — a banca valoriza tuning justificado.

---

## 6. Pseudocódigo

```python
def trend_score_layer1(serie, T, w=7, alpha=1, H=60, lam=1.0, eps=1e-6):
    R = serie[T-w+1 : T+1].sum()
    P = serie[T-2*w+1 : T-w+1].sum()
    growth = (R + alpha) / (P + alpha)
    volume = log(1 + R)
    hist = serie[T-H-w+1 : T-w+1]           # histórico antes da janela
    mu, sigma = hist.mean(), hist.std()
    z = (R / w - mu) / (sigma + eps)
    return volume * log(growth) + lam * max(0, z)

def surprise_layer2(real_T, pred_T, sigma_resid, eps=1e-6):
    return (real_T - pred_T) / (sigma_resid + eps)   # surprise_z
```

---

## 7. Validação (backtest)

1. Escolher uma **tendência conhecida** já presente no corpus (ex.: lançamento de um modelo de IA, anúncio de produto — categorias `inteligencia-artificial`, `pro`, `reviews` têm volume).
2. Rodar o pipeline fixando `T` = **logo antes** do surto.
3. Verificar que o `TrendScore` e/ou `surprise_z` do tópico **sobem** nas janelas seguintes.
4. Reportar qualitativamente o acerto (não há rótulo perfeito — honestidade > número inflado).

---

## 8. Insights da sessão (key insights)

- **Crescimento sozinho engana** → precisa de volume amortecido + suporte mínimo contra ruído de clusters pequenos.
- **`log(growth)` é elegante**: positivo cresce / negativo encolhe, sem `if`.
- **A LSTM ganha propósito de produto** ao virar "detector de surpresa", não experimento solto — resolve a tensão entre "requisito de DL" e "séries curtas".
- **A camada estatística é o seguro**: se a LSTM não performar, o produto ainda ranqueia tendências e a banca vê rigor.

---

## 9. Próximos passos

1. **@architect** registra como ADR (decisão de arquitetura do score).
2. **@pm** incorpora ao PRD como requisito funcional (FR do "Tópicos em Ascensão" + alerta).
3. **@dev** implementa Camada 1 primeiro (entrega valor cedo), depois Camada 2.
