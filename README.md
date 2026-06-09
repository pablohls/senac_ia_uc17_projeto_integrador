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
src/
  coleta/        # coleta de dados (sitemap → dataset)
  pln/           # limpeza e embeddings
  modelagem/     # clustering de tópicos
  dashboard/     # app Streamlit
docs/            # planejamento e design
dados/           # dataset (não versionado — reprodutível)
```

## Como rodar a prova de conceito da coleta

```bash
pip install -r requirements.txt

# Listar artigos datados dos últimos 2 meses (rápido, sem baixar texto):
python src/coleta/backfill_olhardigital.py --meses 2 --sem-texto

# Coletar texto dos últimos 4 meses (precisa de trafilatura):
python src/coleta/backfill_olhardigital.py --meses 4 --limite 50
```

## Stack

Python 3.12 · PyTorch · Sentence-Transformers · BERTopic · Streamlit · Plotly · NetworkX

## Time

Projeto desenvolvido por 4 integrantes como entrega final da UC17.

## Ética & LGPD

A coleta usa apenas dados públicos/editoriais, respeita `robots.txt` e os Termos de Uso
dos portais, aplica rate-limiting e **não armazena dados pessoais (PII)**.
