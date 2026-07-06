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
  common/        # utilidades compartilhadas (io, config)
  coleta/        # Fase 1: coleta via sitemap → corpus.parquet (contrato A1)
  pln/           # Fase 2: limpeza/normalização + embeddings
  modelagem/     # Fase 2: clustering de tópicos (BERTopic) + atribuição (contrato A3)
  scores/        # Fase 3: séries temporais + Trend Score (L1 estatística + L2 LSTM) + backtest
  dashboard/     # Fase 4: app Streamlit (ranking, drill-down, grafo, alertas)
dados/{raw,processed,topics,scores}/   # artefatos entre fases (contratos A1–A4)
tests/  scripts/  docs/
```

## Como rodar (reprodução do demo)

Pré-requisitos: **Python 3.12** e **Poetry**. Para a GPU, driver NVIDIA com suporte a
CUDA 12.4 (o ambiente foi validado em NVIDIA T1000, driver 573.44). Sem GPU compatível,
o pipeline roda em modo CPU — basta trocar `cu124` por `cpu` no `pyproject.toml`.
Em Apple Silicon (M1/M2/M3), a aceleração MPS/Metal é detectada automaticamente.

```bash
poetry install                                  # 1. cria o ambiente isolado e instala tudo
poetry run trendradar                           # 2. pipeline offline (PLN → tópicos → scores)
poetry run streamlit run src/dashboard/app.py   # 3. abre o dashboard de tendências
```

> O comando 2 parte do **corpus congelado** (`dados/raw/corpus.parquet`). Para
> refazer a coleta do zero (~2h, rate-limit educado): `poetry run trendradar --com-coleta`.
> Validação por backtest (Story 3.4): `poetry run python -m src.scores.backtest`.

> Verificação rápida do ambiente: `poetry run pytest tests/smoke_test.py -s`
> (confirma imports, detecção de GPU e leitura/escrita de Parquet).

## Stack

Python 3.12 · Poetry · PyTorch (CUDA 12.4) · Sentence-Transformers · BERTopic · pandas/pyarrow · statsmodels · Streamlit · Plotly · NetworkX · pydantic

## Guia rápido de Git (para a equipe)

> Para quem está começando: Git é o sistema que guarda o **histórico** do projeto e
> permite que os 4 integrantes trabalhem juntos sem sobrescrever o trabalho um do outro.
> Pense num "salvar com histórico" compartilhado. Rode os comandos no terminal, dentro
> da pasta do projeto. **Em caso de dúvida, pergunte antes de `push` — é difícil desfazer.**

### 1. Primeira vez (configuração — faz só uma vez por máquina)

```bash
# Clonar (baixar) o repositório para a sua máquina
git clone https://github.com/pablohls/senac_ia_uc17_projeto_integrador.git
cd senac_ia_uc17_projeto_integrador

# Se identifique (aparece nos seus commits) — use seu nome e e-mail
git config --global user.name  "Seu Nome"
git config --global user.email "voce@email.com"
```

### 2. Fluxo do dia a dia

```bash
git pull                 # ANTES de começar: baixa o que os colegas enviaram
git status               # mostra o que você mudou (vermelho = não salvo no git)
git add nome_do_arquivo  # marca um arquivo para o próximo commit (ou `git add .` p/ todos)
git commit -m "feat: descreve o que você fez"   # "salva com histórico" localmente
git push                 # envia seus commits para o GitHub (compartilha com a equipe)
```

> Ordem mental: **pull** (pega novidades) → trabalhe → **add** → **commit** → **push** (envia).
> Sempre dê `pull` antes de `push` para evitar conflitos.

### 3. Trabalhando com branches (ramos)

Um *branch* é uma "linha de trabalho paralela" — você mexe na sua parte sem afetar a
versão principal (`main`) até estar pronto.

```bash
git checkout -b minha-feature   # cria um branch novo e já entra nele
git checkout main               # volta para o branch principal
git branch                      # lista seus branches (o atual tem um *)
git merge minha-feature         # (estando na main) traz o trabalho do branch para a main
```

### Referência rápida

| Comando | O que faz |
|---|---|
| `git clone <url>` | Baixa o repositório pela primeira vez |
| `git pull` | Atualiza sua cópia com o que está no GitHub |
| `git status` | Mostra arquivos alterados / pendentes |
| `git add <arquivo>` | Prepara um arquivo para o commit (`git add .` = todos) |
| `git commit -m "msg"` | Salva as mudanças no histórico local |
| `git push` | Envia seus commits para o GitHub |
| `git checkout -b <nome>` | Cria e entra em um branch novo |
| `git checkout <nome>` | Troca para um branch existente |
| `git log --oneline` | Mostra o histórico de commits resumido |
| `git diff` | Mostra exatamente o que você mudou |

> **Padrão de mensagem de commit:** comece com o tipo — `feat:` (novo), `fix:` (correção),
> `docs:` (documentação), `chore:` (manutenção). Ex.: `git commit -m "feat: coletor de sitemap"`.

## Time

Projeto desenvolvido por 4 integrantes como entrega final da UC17.

## Ética & LGPD

A coleta usa apenas dados públicos/editoriais, respeita `robots.txt` e os Termos de Uso
dos portais, aplica rate-limiting e **não armazena dados pessoais (PII)**.

Discussão completa (coleta responsável, LGPD, anonimização, risco de alarme falso e
mitigações) e o estudo de caso de uma tendência detectada:
[`docs/estudo-de-caso-etica-lgpd.md`](docs/estudo-de-caso-etica-lgpd.md).
