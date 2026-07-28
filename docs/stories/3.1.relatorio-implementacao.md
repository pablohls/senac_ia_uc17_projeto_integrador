# Story 3.1 — Séries Temporais por Tópico

**Status:** ✅ PRONTO PARA TESTES  
**Owner:** Integrante D (Fase 3 — Scores)  
**Dificuldade:** 🟡 Moderada (aprende com pareamento leve)

---

## O Que Foi Implementado

### 1. **`src/scores/series.py`** — Lógica pura

Implementa a função central `montar_series(doc_topics, gerar_weekly=True)`:

```python
def montar_series(doc_topics: pd.DataFrame, *, gerar_weekly: bool = True) -> pd.DataFrame:
    """Monta série de frequência diária de cada tópico com zero-fill.
    
    Entradas:
    - doc_topics: {doc_id, data, topic_id}
    
    Saída:
    - Series: {topic_id, data, count[, count_weekly]}
      com ZERO-FILL para todos os dias do período
    """
```

**Características:**
- ✅ **Zero-fill:** preenche com 0 os dias sem menção (crítico para Story 3.2)
- ✅ **Resample semanal:** agregação opcional para tópicos esparsos
- ✅ **Determinístico:** entrada fixa → saída fixa (testável)
- ✅ **Puro:** separado de I/O (não escreve arquivo)
- ✅ **Validador:** função `validar_serie()` integrada

**Acceptance Criteria atendidos:**
- ✅ **AC1:** Série de contagem diária por tópico no período do corpus
- ✅ **AC2:** Agregação semanal disponível (`count_weekly`)
- ✅ **AC3:** Dias sem menção preenchidos com zero (zero-fill)

### 2. **`tests/test_series.py`** — Testes unitários

19 testes cobrindo:

```
TestMontarSeries (10 testes)
├── test_ac1_contagem_diaria        ✅ AC1
├── test_ac3_zero_fill               ✅ AC3
├── test_ac2_agregacao_semanal       ✅ AC2
├── test_determinismo                ✅ Reprodutibilidade
├── test_ordenacao                   ✅ Ordem esperada
├── test_erro_vazio                  ✅ Input validation
├── test_erro_colunas_faltando       ✅ Input validation
├── test_com_datas_strings_iso       ✅ Flexibilidade
├── test_com_outliers_topic_minus_1  ✅ Outliers (-1)
└── test_flow_completo               ✅ Integração

TestValidarSerie (4 testes)
├── test_serie_valida
├── test_serie_vazia
└── test_nao_zero_filled

TestIntegration (1 teste)
└── test_flow_completo               ✅ E2E
```

### 3. **`src/scores/run.py`** — Orquestrador

Coordena a execução isolada (ou integrada no pipeline):

```python
def main() -> None:
    """Flow:
    1. Carrega config.yaml (pydantic)
    2. Lê doc_topics.parquet (entrada Fase 3)
    3. Executa Story 3.1 (montar_series)
    4. Persiste series.parquet
    5. Log estruturado
    """
```

**Uso:**
```bash
# Isolado (desenvolvimento)
poetry run python -m src.scores.run

# Integrado (pipeline completo)
poetry run sonar  # (quando run_all.py chamar)
```

---

## Como Testar Localmente

### 1. **Setup (primeira vez)**
```bash
# Clone e setup
git clone https://github.com/pablohls/senac_ia_uc17_projeto_integrador.git
cd senac_ia_uc17_projeto_integrador
poetry install

# Troque para o branch
git checkout feat/3-scores-fase3
```

### 2. **Rode os testes**
```bash
# Todos os testes da Story 3.1
poetry run pytest tests/test_series.py -s

# Teste específico
poetry run pytest tests/test_series.py::TestMontarSeries::test_ac1_contagem_diaria -s

# Com cobertura
poetry run pytest tests/test_series.py --cov=src.scores.series
```

**Esperado:** 19/19 testes ✅ passando

### 3. **Rode o script (requer doc_topics.parquet)**

Se você tiver a saída da Fase 3 em `dados/topics/doc_topics.parquet`:

```bash
poetry run python -m src.scores.run
```

**Output:**
```
============================================================
Fase 4 — Scores (Stories 3.1 a 3.4)
============================================================
Carregando configuração...
  Config OK. Trend Score params: w=7, alpha=1.0, H=60
Lendo dados/topics/doc_topics.parquet...
  ✓ 12345 documentos lidos

--- Story 3.1: Montar séries temporais ---
  ✓ Séries montadas: 450 linhas
  Tópicos únicos: 45
  Período: 2026-01-01 a 2026-02-15
  ✓ Persistido: /path/to/dados/scores/series.parquet
============================================================
```

### 4. **Lint/Format**
```bash
# Verificar código
poetry run ruff check src/scores/series.py tests/test_series.py

# Formatar automaticamente
poetry run ruff format src/scores/
```

---

## Estrutura de Arquivos Criados

```
feat/3-scores-fase3/
├── src/scores/
│   ├── __init__.py         (existia)
│   ├── series.py           ✨ NEW — Lógica principal (~170 linhas)
│   └── run.py              ✨ NEW — Orquestrador (~80 linhas)
└── tests/
    └── test_series.py      ✨ NEW — 19 testes (~280 linhas)

Artefatos (produzidos em runtime):
└── dados/scores/
    └── series.parquet      ← Output da Story 3.1 (zero-filled)
```

---

## Contrato de Artefato (Saída)

**Arquivo:** `dados/scores/series.parquet`

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `topic_id` | int64 | Identificador do tópico |
| `data` | object (date) | Data (ISO) |
| `count` | int64 | Nº de documentos no dia |
| `count_weekly` | int64 | Nº de documentos na semana (opcional) |

**Garantias:**
- ✅ Zero-filled: todos os dias [data_min, data_max] existem para cada tópico
- ✅ Ordenado: topic_id ASC, depois data ASC
- ✅ Determinístico: mesma entrada → mesma saída

**Exemplo (primeiras 10 linhas):**
```
topic_id  data        count  count_weekly
0         2026-01-01  2      12
0         2026-01-02  1      12
0         2026-01-03  0      12
0         2026-01-04  3      12
0         2026-01-05  6      12
1         2026-01-01  0      8
1         2026-01-02  2      8
1         2026-01-03  3      8
1         2026-01-04  0      8
1         2026-01-05  3      8
```

---

## Por Que Zero-Fill é Crítico

A Story 3.2 (Trend Score Camada 1) usa **z-score** para detectar anomalias:

```
z = (R/w − μ) / (σ + ε)
```

Se não preencher com zero:
- ❌ Dias sem menção ficam faltando
- ❌ `σ` (desvio-padrão) fica errado
- ❌ Alertas falsos/perdidos

Com zero-fill:
- ✅ Série completa [data_min, data_max]
- ✅ `σ` calculado corretamente
- ✅ Detecção de anomalias funciona

---

## Próximas Stories (em desenvolvimento)

- **Story 3.2:** Trend Score Camada 1 (estatístico)
  - Lê: `series.parquet`
  - Escreve: `scores.parquet`
  
- **Story 3.3:** Trend Score Camada 2 (LSTM)
  - Lê: `series.parquet`, `scores.parquet`
  - Escreve: colunas adicionais em `scores.parquet`, `alerts.json`
  
- **Story 3.4:** Validação por backtest
  - Lê: `series.parquet`, `scores.parquet`
  - Produz: relatório qualitativo (markdown + figuras)

---

## Referências

- **Spec:** `docs/stories/3.1.series-temporais-por-topico.md`
- **Arquitetura:** `docs/architecture.md` (Contratos A4)
- **Design:** `docs/design/trend-score.md` (§2)

---

## Checklist para Code Review

Antes de fazer merge, verifique:

- [ ] Todos os 19 testes passam
- [ ] `ruff check` e `ruff format` OK
- [ ] Docstrings em todas as funções
- [ ] Sem números mágicos (parâmetros via config)
- [ ] `doc_id` nunca é modificado/reordenado
- [ ] Zero-fill é garantido (linha 1–100 linhas depois)
- [ ] Determinismo validado (teste de reprodutibilidade)

---

**Pronto para PR & merge! 🚀**
