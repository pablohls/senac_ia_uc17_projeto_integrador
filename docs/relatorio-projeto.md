# SONAR — Relatório do Projeto

**Sistema de Observação de Narrativas e Assuntos Relevantes**
Projeto Integrador — SENAC UC17 (Inteligência Artificial)
Data do relatório: 2026-07-10 · Estado: 26/26 stories Done, backlog zerado

> Documento-irmão: o **[Guia do Desenvolvedor](guides/guia-do-desenvolvedor.md)** explica em detalhe *como* e *por que* cada parte foi construída. Este relatório responde *o que o SONAR faz* e *quais são suas capacidades*.

---

## 1. O que é o SONAR

O SONAR é um pipeline de **PLN + Deep Learning + IA Generativa** que detecta tendências emergentes em notícias de tecnologia em português brasileiro. Ele coleta artigos de portais de tecnologia (Olhar Digital e Canaltech), descobre automaticamente **sobre o que** se está falando (tópicos), mede **o quanto cada assunto está acelerando** (Trend Score) e, desde a Fase 5, **explica em linguagem natural por que cada tendência está subindo** e permite conversar com o corpus via chat com citação de fontes.

**O problema que resolve:** o setor de tecnologia produz centenas de notícias por dia em dezenas de portais. Profissionais que precisam antecipar tendências (analistas de inovação, criadores de conteúdo, jornalistas) fazem esse acompanhamento manualmente, percebem movimentos tarde e sem medição objetiva. Ferramentas como Google Trends medem volume de *busca* (não cobertura editorial), não agrupam temas automaticamente em português técnico e entregam curvas sem explicação.

**Pipeline em uma linha:**

```
Coleta (sitemap) → PLN (limpeza + embeddings) → BERTopic (tópicos)
   → Trend Score (L1 estatística + L2 LSTM) → Dashboard + IA Generativa (LLM local)
```

---

## 2. Capacidades

### 2.1 Coleta de dados (Fase 1)
- Coleta **educada** (NFR4) via sitemap XML de dois portais PT-BR: User-Agent identificado, rate-limit ~1 req/s, respeito ao robots.txt.
- Janela histórica configurável (4 meses), extração de texto limpo com trafilatura, deduplicação em 3 camadas.
- **Modo incremental**: recoletas diárias baixam apenas URLs novas (minutos em vez de ~6h).
- Corpus **multi-fonte congelado** em Parquet (contrato A1, 16.148 artigos) — o demo é 100% reprodutível offline.

### 2.2 Descoberta e nomeação de tópicos (Fase 2)
- Embeddings semânticos multilíngues (Sentence-Transformers `paraphrase-multilingual-mpnet-base-v2`, 768d, GPU).
- Clustering não supervisionado **BERTopic** (UMAP → HDBSCAN → c-TF-IDF): descobre o número de tópicos sozinho, isola ruído em outliers, nomeia cada tópico pelos termos característicos.
- **Filtro de catálogo:** páginas `/produto/` do Canaltech (specs de aparelho, não notícia) são excluídas da modelagem via `corpus_analise.excluir_url_contendo` (~4.923 artigos), mantidas no corpus bruto — decisão configurável e reversível.
- Resultado atual: **213 tópicos** sobre o corpus multi-fonte de análise (11.225 artigos); **coerência de 93,3%** validada em avaliação humana na modelagem original (limiar da métrica de sucesso: 70%).

### 2.3 Medição de tendência em duas camadas (Fase 3 — ADR-001)
- **Base temporal filtrada:** as séries usam apenas fontes de data confiável (`analise_temporal.fontes_confiaveis: [olhar_digital]`, 6.702 artigos). O Canaltech é excluído da contagem temporal por derivar a data do `<lastmod>` do sitemap (DATA-001), mas segue nos tópicos e no chat RAG.
- **Camada 1 (estatística, determinística):** `TrendScore = log(1+R)·log(growth) + λ·max(0,z)` — combina volume, crescimento semana-sobre-semana (com suavização de Laplace) e surto vs. a própria história do tópico. Guardas contra ruído (`n_min=5`, badge "novo").
- **Camada 2 (Deep Learning):** uma **LSTM por tópico** prevê o próximo ponto da série; a diferença entre real e previsto vira um **score de surpresa** (`surprise_z`), sempre comparado a um baseline de persistência com MAE/RMSE em hold-out (honestidade científica, NFR6). `surprise_z > 2.5` gera alerta de anomalia.
- **Backtest sem vazamento de futuro** valida o sistema "congelado no tempo": o tópico 139 saiu de fora do ranking para 1º lugar (score 8,07) exatamente na semana do surto real de cobertura.

### 2.4 IA Generativa local (Fase 5 — ADR-002)
- **Analista IA (batch):** para cada tópico em ascensão, um LLM gera rótulo semântico curto e um parágrafo "por que está subindo", com base apenas nos artigos do tópico (37 briefings no artefato atual).
- **Chat RAG:** conversa com o corpus — recuperação por similaridade de cosseno sobre os embeddings já existentes, resposta restrita aos trechos recuperados, **citações clicáveis** das matérias originais e recusa honesta quando não há base.
- **100% local e soberano:** Ollama servindo `qwen2.5:14b` (líder PT-BR no Open PT-LLM Leaderboard, validado por benchmark próprio) — nenhum dado sai da máquina (LGPD), custo zero, demo offline. Falha do LLM **nunca** derruba o pipeline (degradação graciosa em 3 níveis).

### 2.5 Dashboard (Fases 4 e 6)
- Streamlit com tema dark SONAR: cards de métricas, ranking "🔥 Em Alta", alertas de anomalia 🚨, drill-down por tópico (análise da IA, série temporal, termos, artigos-fonte), série semanal, "pontes entre tópicos" e grafo de co-ocorrência de termos.
- Padrão **precompute-then-serve**: o dashboard só lê artefatos pré-computados — tela principal em <5s (NFR8).

### 2.6 Qualidade e reprodutibilidade
- **172 testes automatizados verdes**; funções de lógica puras e testáveis, separadas da casca de I/O.
- Reprodutibilidade de ponta a ponta: seeds fixas (42), config central sem números mágicos (`config/config.yaml` + pydantic), manifesto de execução (`dados/run_manifest.json`) com hash da config.
- 26 stories com quality gates formais: **21 PASS, 4 CONCERNS (não-bloqueantes), 1 WAIVED** — todos justificados em `docs/qa/`.

---

## 3. Requisitos atendidos

| Requisito | Status |
|---|---|
| FR1–FR10 (coleta, dataset congelado, limpeza, embeddings, tópicos, séries, Trend Score, LSTM, alertas, dashboard) | ✅ Atendidos, com evidência em gates |
| FR11 (filtros por categoria/janela) — COULD | ⚠️ Parcial: drill-down entregue; filtro por categoria sem evidência de fechamento |
| NFR1 stack 100% open-source · NFR2 GPU local · NFR3 demo offline reprodutível · NFR4 coleta ética/LGPD · NFR5 código modular · NFR6 LSTM vs. baseline · NFR7 priorização MoSCoW · NFR8 dashboard <5s | ✅ Todos atendidos |

Métricas de sucesso do PRD: corpus ≥4.000 artigos (✅ 16.148 brutos / 11.225 de análise, multi-fonte), coerência ≥70% (✅ 93,3%), ranking demonstrável (✅), LSTM sempre vs. baseline (✅), ≥1 backtest (✅ 2), demo <2 min de setup (✅ 3 comandos).

---

## 4. Números do projeto

| Indicador | Valor |
|---|---|
| Artigos no corpus bruto (A1, run 2026-07-10) | **16.148** (Canaltech 9.446 + Olhar Digital 6.702) |
| Artigos na análise (após excluir catálogo `/produto/`) | **11.225** |
| Artigos na análise temporal (só Olhar Digital, data confiável) | **6.702** |
| Tópicos descobertos | **213** (coerência 93,3% na modelagem original) |
| Briefings gerados pela IA | 37 tópicos em ascensão |
| Alertas de anomalia (série do Olhar Digital) | 0 (após filtro DATA-001) |
| Testes automatizados | 172 verdes |
| Stories entregues | 26/26 (6 epics) |
| Dimensão dos embeddings | 768 (matriz N×768, GPU) |
| Fontes de dados | 2 portais (sitemaps oficiais) |

> Os números refletem o run multi-fonte de 2026-07-10 (coleta das duas fontes concluída). Os três recortes de corpus (bruto/análise/temporal) são controlados por listas configuráveis no `config.yaml` e registrados no `run_manifest.json`.

---

## 5. Stack tecnológica

Python 3.12 + Poetry. Principais: `torch` (LSTM, CUDA 12.4), `sentence-transformers` (embeddings), `bertopic` (tópicos), `pandas`/`pyarrow` (contratos Parquet), `streamlit`/`plotly`/`networkx` (dashboard), `pydantic` (config validada), `trafilatura`/`lxml`/`requests` (coleta), `openai` (cliente LLM OpenAI-compatible → Ollama local `qwen2.5:14b`). 100% gratuita/open-source (NFR1).

---

## 6. Como rodar o demo

```bash
poetry install                                     # cria o venv e instala tudo
poetry run sonar                                   # pipeline PLN + scores (corpus congelado, sem rede)
poetry run streamlit run src/dashboard/app.py      # dashboard
# opcional (IA generativa): ollama serve + ollama pull qwen2.5:14b
# coleta completa das 2 fontes (~6h, rate-limit educado): poetry run sonar --com-coleta
```

---

## 7. Limitações conhecidas (transparência para a banca)

1. **Data do Canaltech** vem do `<lastmod>` do sitemap (não é a data de publicação exata), concentrando ~54% dos artigos no dia da coleta (DATA-001) — **tratado** excluindo o Canaltech da análise temporal (`analise_temporal.fontes_confiaveis`), o que zerou os 118 alertas espúrios; a fonte segue nos tópicos e no chat.
2. **Stopwords residuais** no c-TF-IDF degradam poucos dos 213 tópicos — mitigado pelos rótulos LLM da Story 5.2, com fallback automático (`_label_suspeito`) quando o LLM devolve rótulo corrompido.
3. **Avaliação cega humana** do benchmark de LLM foi formalmente dispensada (WAIVED) — o vencedor coincidiu com o default do ADR-002 e a planilha está pronta para execução a posteriori.
4. **Séries curtas** (~4 meses) limitam a base histórica do burst e o treino da LSTM — mitigado por guardas (`sigma_min`, `k=2.5`) e coleta incremental que alonga a série com o tempo.
5. Chat RAG **sem memória conversacional** e recuperação por artigo inteiro (não por chunk) — escopos conscientes, documentados.

A lista completa, com mitigação de cada item, está no Guia do Desenvolvedor.
