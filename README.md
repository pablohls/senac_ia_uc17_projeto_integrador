# SONAR — Sistema de Observação de Narrativas e Assuntos Relevantes

Projeto Integrador final do curso de **Inteligência Artificial (1200h) — SENAC / UC17**.

O **SONAR** é um pipeline de PLN + Deep Learning que monitora portais de tecnologia
em português, agrupa automaticamente as notícias por assunto e identifica **quais tópicos
estão ganhando tração** — sinalizando tendências emergentes antes que se tornem óbvias.

> **Nota de marca:** o projeto nasceu com o codinome interno *TrendRadar* e foi
> rebatizado **SONAR** em 2026-07-09 — nome do pacote, comandos e documentação foram
> unificados. Documentos históricos podem citar o codinome de época; o artefato
> congelado do benchmark (`avaliacao_cega.csv`) o preserva por reprodutibilidade.

## Visão geral do pipeline

```
Coleta (sitemap) → PLN (limpeza + embeddings) → Modelagem (BERTopic) → Trend Score → Dashboard + IA Generativa
```

1. **Coleta** — notícias datadas via sitemap de portais (Olhar Digital, Canaltech).
2. **PLN** — limpeza/normalização + embeddings semânticos (Sentence-Transformers, PT).
3. **Modelagem** — tópicos não supervisionados (UMAP → HDBSCAN → c-TF-IDF) via BERTopic.
4. **Trend Score** — 2 camadas:
   - **Camada 1 (estatística):** ranqueia os "Tópicos em Ascensão".
   - **Camada 2 (LSTM):** detecta surtos além do previsto (anomalia/sinal forte).
5. **Dashboard** — Streamlit com tópicos em ascensão, pontes entre tópicos e alertas.
6. **IA Generativa (Fase 5)** — LLM local via Ollama: **Analista IA** (briefings "por que
   este tópico sobe", em lote) e **chat RAG** que responde perguntas sobre o corpus com
   citação das fontes — e recusa honestamente o que o corpus não cobre.

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
  common/        # utilidades compartilhadas (io, config, cliente LLM OpenAI-compatible)
  coleta/        # Fase 1: coleta via sitemap → corpus.parquet (contrato A1)
  pln/           # Fase 2: limpeza/normalização + embeddings
  modelagem/     # Fase 2: clustering de tópicos (BERTopic) + atribuição (contrato A3)
  scores/        # Fase 3: séries temporais + Trend Score (L1 estatística + L2 LSTM) + backtest
  dashboard/     # Fase 4: app Streamlit (ranking, drill-down, pontes entre tópicos, alertas)
  insight/       # Fase 5: Analista IA — briefings "por que sobe" em lote (LLM local)
  rag/           # Fase 5: RAG — retriever semântico + resposta com citação de fontes
dados/{raw,processed,topics,scores,insight}/   # artefatos entre fases (contratos A1–A5)
tests/  scripts/  docs/
```

## Como rodar (reprodução do demo)

Pré-requisitos: **Python 3.12** e **Poetry**. Nada além de `poetry install` é necessário
em nenhuma plataforma — as wheels oficiais do PyTorch já são específicas por sistema, e
**ninguém precisa editar o `pyproject.toml`**.

| Sua máquina | O que você ganha | Precisa fazer algo? |
|---|---|---|
| **Linux + NVIDIA** | GPU via CUDA 12.4 (validado em T1000, driver 573.44) | Só ter o driver com suporte a CUDA 12.4 |
| **macOS Apple Silicon** (M1/M2/M3) | GPU via MPS/Metal, detectada sozinha | Não |
| **Windows** | CPU (as wheels do PyPI p/ Windows são CPU-only) | Só se quiser GPU — ver abaixo |
| **Qualquer uma sem GPU** | CPU, com fallback automático | Não |

<details>
<summary><b>Windows + placa NVIDIA:</b> como habilitar a GPU (opcional)</summary>

Instale o torch CUDA **dentro do venv**, sem tocar no `pyproject.toml` (assim você não
quebra o ambiente de quem está em Mac/Linux):

```powershell
poetry install
poetry run pip install torch==2.6.0+cu124 --index-url https://download.pytorch.org/whl/cu124
```

O `poetry install` volta a sobrescrever isso; basta repetir a segunda linha quando ocorrer.
Alternativa mais estável: rodar o projeto no **WSL2 (Ubuntu)**, onde a wheel padrão do PyPI
já vem com CUDA 12.4 e nada disso é necessário.

</details>

```bash
poetry install                                  # 1. cria o ambiente isolado e instala tudo
poetry run sonar                                # 2. pipeline offline (PLN → tópicos → scores)
poetry run streamlit run src/dashboard/app.py   # 3. abre o dashboard de tendências
```

> **Atalhos:** há um `Makefile` com os alvos mais usados — `make up` sobe o Ollama (+ modelo)
> e o dashboard de uma vez, `make demo` roda o pipeline antes disso, `make test` roda a
> suíte, `make help` lista tudo. Funciona em **Linux e macOS**; no Windows use os comandos
> `poetry run` acima (o Makefile depende de `pgrep`/`pkill`) ou rode dentro do WSL2.

> Os artefatos de dados (corpus congelado, tópicos, scores, briefings e índice de
> embeddings) são **versionados no repositório** — um clone limpo já abre o dashboard
> (passo 3) sem precisar do passo 2. Rode o passo 2 para regenerar tudo do zero.

> O comando 2 parte do **corpus congelado** (`dados/raw/corpus.parquet`). Para
> atualizar a coleta: `poetry run sonar --com-coleta` — o modo é **incremental**
> (baixa só os artigos novos e agrega ao corpus; minutos, não horas). Reconstrução
> total: `poetry run python -m src.coleta.extract --completo` (~2h, rate-limit educado).
> Validação por backtest (Story 3.4): `poetry run python -m src.scores.backtest`.

> Verificação rápida do ambiente: `poetry run pytest tests/smoke_test.py -s`
> (confirma imports, detecção de GPU e leitura/escrita de Parquet).

### Fase 5 — IA generativa (Analista IA + chat RAG)

> **Esta fase é opcional.** O dashboard e todo o pipeline funcionam sem nenhum LLM — as
> seções de IA exibem um fallback, e os briefings já versionados continuam sendo lidos
> normalmente. Instale o Ollama só se quiser **regenerar** análises ou usar o chat RAG.

Os recursos de LLM (aba "🧠 Análise" e o chat RAG) usam um modelo **local** servido pelo
[Ollama](https://ollama.com).

**1. Instalar o Ollama** — escolha a sua plataforma:

```bash
curl -fsSL https://ollama.com/install.sh | sh   # Linux
brew install ollama && brew services start ollama   # macOS (ou baixe o .dmg do site)
winget install Ollama.Ollama                    # Windows (ou baixe o .exe do site)
```

**2. Baixar o modelo e (opcionalmente) regenerar os briefings:**

```bash
ollama pull qwen2.5:14b                         # ~9 GB (modelo validado no ADR-002)
poetry run python -m src.insight.run            # opcional: regenera os briefings
```

- **Hardware:** o `qwen2.5:14b` (Q4) usa **~11 GB de VRAM** (validado em GPU de 16 GB).
  Em GPUs menores o Ollama divide com a RAM (funciona, porém lento). Em Macs Apple Silicon
  a memória é unificada — 16 GB rodam, com folga menor. Máquina sem capacidade? Duas saídas
  sem tocar no código: apontar `base_url` para um endpoint remoto OpenAI-compatible, ou usar
  um modelo menor (ex.: `qwen2.5:7b`) — neste caso a qualidade **deixa de corresponder** ao
  benchmark do ADR-002, então registre isso ao comparar resultados.
- **Configuração:** endpoint e modelo em `config/config.yaml → insight`
  (`base_url: http://localhost:11434/v1`, `model: qwen2.5:14b`). Para endpoint remoto,
  troque `base_url`/`model` e exporte a chave na env var `LLM_API_KEY` (com Ollama local
  não é preciso chave).
- Os briefings prontos (`dados/insight/briefings.parquet`) e o índice do RAG
  (`dados/processed/embeddings_index.parquet`) já vêm versionados — o passo 3 só é
  necessário após regenerar tópicos/scores.
- A escolha do modelo foi validada por benchmark empírico A/B/C
  ([`docs/research/2026-07-08-benchmark-llm-local/resultado-benchmark.md`](docs/research/2026-07-08-benchmark-llm-local/resultado-benchmark.md)).

## Stack

Python 3.12 · Poetry · PyTorch 2.6 (CUDA 12.4 no Linux · MPS no Apple Silicon · CPU no Windows) · Sentence-Transformers · BERTopic · pandas/pyarrow · statsmodels · Streamlit · Plotly · NetworkX · pydantic · Ollama + SDK OpenAI (LLM local opcional, endpoint OpenAI-compatible)

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

### 4. Socorro: `git pull` deu "diverged" ou conflito estranho

Se o `pull` reclamar que os históricos **divergiram** sem você ter feito nada de errado,
provavelmente alguém **reescreveu o histórico** da `main` (mudar mensagens de commit, limpar
metadados). Isso troca o identificador (*hash*) de todos os commits: o conteúdo é o mesmo,
mas o Git passa a ver as duas versões como histórias diferentes.

**Antes de qualquer coisa, descubra se você tem trabalho que só existe na sua máquina.**
Este comando compara pelo *conteúdo* das mudanças, então funciona mesmo com os hashes
trocados:

```bash
git fetch origin
git cherry -v origin/main main    # lista o que existe só aqui; nada listado = nada exclusivo
```

**Salve os arquivos locais não versionados antes do reset.** O `reset --hard` apaga do disco
todo arquivo que era rastreado antes e não existe na versão nova — **inclusive os que hoje
estão no `.gitignore`**. É o caso dos documentos internos de processo, que saíram do rastreio
em `c30fe85` para serem "mantidos localmente": eles somem no reset, e como estão ignorados,
**nada aparece no `git status`** para avisar. Faça uma cópia fora do repositório:

```bash
mkdir -p ~/backup-sonar
cp -r docs/handoff-*.md docs/runlogs/ ~/backup-sonar/ 2>/dev/null
```

Depois do reset, devolva ao lugar com `cp -r ~/backup-sonar/* docs/` (eles voltam a ser
ignorados pelo git, sem sujar o repositório).

- **Nada foi listado** → você não tem trabalho exclusivo. Pode re-sincronizar:

  ```bash
  git checkout main
  git reset --hard origin/main    # descarta a versão local e adota a do GitHub
  git fetch --prune               # remove referências a branches que já não existem
  ```

- **Apareceu alguma linha** → **não rode o `reset --hard` ainda.** Salve seu trabalho num
  branch antes, senão ele é perdido:

  ```bash
  git branch meu-backup           # guarda seus commits
  git reset --hard origin/main    # agora sim, com o backup feito
  ```

  Depois, traga só o seu trabalho de volta por cima da versão nova:

  ```bash
  git rebase --onto origin/main meu-backup~1 meu-backup
  ```

  Na dúvida sobre o `rebase`, pare e chame alguém — o `meu-backup` mantém tudo salvo.

> ⚠️ Reescrever histórico da `main` obriga **toda a equipe** a fazer isso. Evite; se for
> realmente necessário, avise antes e confirme que ninguém tem trabalho pendente.
> Atenção: se a `main` remota também **avançou** depois da reescrita, o `reset --hard`
> não devolve só os hashes — ele traz conteúdo novo e descarta o seu. Por isso o
> `git cherry` vem primeiro, sempre.

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
