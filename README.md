# TrendRadar — Mapeador de Tendências em Tecnologia

Projeto Integrador final do curso de **Inteligência Artificial (1200h) — SENAC / UC17**.

O **TrendRadar** é um pipeline de PLN + Deep Learning que monitora portais de tecnologia
em português, agrupa automaticamente as notícias por assunto e identifica **quais tópicos
estão ganhando tração** — sinalizando tendências emergentes antes que se tornem óbvias.

## Visão geral do pipeline

```
Coleta (sitemap)  →  PLN (limpeza + embeddings)  →  Modelagem (BERTopic)  →  Trend Score  →  Dashboard
```

1. **Coleta** — notícias datadas via sitemap de portais (Olhar Digital, Canaltech).
2. **PLN** — limpeza/normalização + embeddings semânticos (Sentence-Transformers, PT).
3. **Modelagem** — tópicos não supervisionados (UMAP → HDBSCAN → c-TF-IDF) via BERTopic.
4. **Trend Score** — 2 camadas:
   - **Camada 1 (estatística):** ranqueia os "Tópicos em Ascensão".
   - **Camada 2 (LSTM):** detecta surtos além do previsto (anomalia/sinal forte).
5. **Dashboard** — Streamlit com tópicos em ascensão, grafo de co-ocorrência e alertas.

## Documentação

| Documento | Conteúdo |
|-----------|----------|
| [`docs/brief.md`](docs/brief.md) | Project Brief (problema, escopo, MVP, riscos) |
| [`docs/prd.md`](docs/prd.md) | PRD — requisitos, épicos e stories |
| [`docs/design/trend-score.md`](docs/design/trend-score.md) | Especificação do algoritmo Trend Score |
| [`docs/research/2026-06-08-backfill-historico/findings.md`](docs/research/2026-06-08-backfill-historico/findings.md) | Pesquisa de viabilidade da fonte de dados |

## Estrutura

```
config/          # config.yaml — parâmetros centrais (sem números mágicos no código)
src/
  common/        # utilidades compartilhadas (io, config, logging)
  coleta/        # Fase 1: coleta via sitemap → corpus.parquet
  pln/           # Fase 2: limpeza/normalização + embeddings
  modelagem/     # Fase 3: clustering de tópicos (BERTopic) + atribuição
  scores/        # Fase 4: séries temporais + Trend Score (L1 estatística + L2 LSTM)
  dashboard/     # Fase 5: app Streamlit
dados/{raw,processed,topics,scores}/   # artefatos entre fases (não versionados)
tests/  notebooks/  docs/
```

## Como rodar (reprodução do demo)

Pré-requisitos: **Python 3.12** e **Poetry**. Para a GPU, driver NVIDIA com suporte a
CUDA 12.4 (o ambiente foi validado em NVIDIA T1000, driver 573.44). Sem GPU compatível,
o pipeline roda em modo CPU — basta trocar `cu124` por `cpu` no `pyproject.toml`.

```bash
poetry install            # 1. cria o ambiente isolado e instala tudo (trava versões no poetry.lock)
poetry run trendradar     # 2. executa o pipeline (coleta → PLN → modelagem → scores)
streamlit run src/dashboard/app.py   # 3. abre o dashboard de tendências
```

> Verificação rápida do ambiente: `poetry run pytest tests/smoke_test.py -s`
> (confirma imports, detecção de GPU e leitura/escrita de Parquet).

## Stack

Python 3.12 · Poetry · PyTorch (CUDA 12.4) · Sentence-Transformers · BERTopic · pandas/pyarrow · statsmodels · Streamlit · Plotly · NetworkX · pydantic

## Time

Projeto desenvolvido por 4 integrantes como entrega final da UC17.

## Ética & LGPD

A coleta usa apenas dados públicos/editoriais, respeita `robots.txt` e os Termos de Uso
dos portais, aplica rate-limiting e **não armazena dados pessoais (PII)**.
