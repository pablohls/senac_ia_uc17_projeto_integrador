# SONAR — Mapeador de Tendências em Tecnologia: Product Requirements Document (PRD)

> **Autor:** @pm (Morgan) | **Modo:** YOLO | **Data:** 2026-06-08
> **Entradas:** `docs/brief.md`, `docs/research/2026-06-08-backfill-historico/findings.md`, `docs/design/trend-score.md`
> **Contexto:** Projeto Integrador final — Curso de IA (1200h) | Prazo: ~2 semanas | 4 integrantes | 1 GPU local
> **Próximo:** Handoff para @architect (arquitetura) → @sm (stories)

---

## Goals and Background Context

### Goals

- Entregar, em 2 semanas, um pipeline ponta a ponta funcional (coleta → PLN → modelagem → dashboard) demonstrável ao vivo sobre dataset congelado.
- Detectar automaticamente "Tópicos em Ascensão" no setor de Tecnologia/Ciência a partir de notícias datadas.
- Integrar explicitamente ≥ 4 disciplinas do curso: PLN, embeddings/Transformers, clustering não supervisionado e redes neurais (LSTM).
- Produzir um estudo de caso de uma tendência real detectada, com narrativa do "porquê".
- Garantir um MVP robusto mesmo se o deep learning sequencial (LSTM) não performar — via Trend Score estatístico (Camada 1) como plano B.
- Documentar decisões técnicas, incluindo experimentos que falharam e ajustes de rota.

### Background Context

Profissionais que dependem de antecipar tendências em tecnologia (analistas de inovação, criadores de conteúdo, PMs) hoje acompanham dezenas de portais manualmente e percebem movimentos tarde demais, sem medição objetiva de crescimento. O **SONAR** automatiza isso: descobre tópicos sozinho (sem taxonomia pré-definida), mede o crescimento de cada um ao longo do tempo e sinaliza os emergentes num dashboard.

A pesquisa de viabilidade confirmou que a fonte original (Twitter/X) é inviável em 2026 e que o **sitemap mensal datado dos portais** (Olhar Digital validado ao vivo: ~1.5–2k artigos/mês, granularidade diária) resolve o histórico temporal. O núcleo algorítmico foi definido como um **Trend Score de 2 camadas** (estatístico robusto + surpresa de previsão por LSTM). Este é um **Projeto Integrador acadêmico** (Curso de IA, 1200h), com restrições firmes: ~2 semanas até a banca, 4 integrantes e 1 GPU local — o que torna a priorização MUST > SHOULD > COULD e o plano B (Camada 1 estatística) decisões centrais, não detalhes.

### Success Metrics

Critérios mensuráveis de sucesso para a banca (avaliados sobre o dataset congelado):

- **SM1 — Corpus:** ≥ 4.000 artigos datados coletados de ≥ 1 portal, cobrindo ≥ 4 meses. *(PoC já provou 2.271 em 2 meses.)*
- **SM2 — Qualidade de tópicos:** ≥ 70% dos tópicos avaliados manualmente julgados coerentes (rótulo c-TF-IDF condizente).
- **SM3 — Trend Score (Camada 1):** ranking de "Tópicos em Ascensão" produzido e demonstrável; função coberta por teste unitário.
- **SM4 — Honestidade científica (Camada 2):** LSTM **sempre** reportada com MAE/RMSE em hold-out **contra baseline** — métrica reportada vale como sucesso, independentemente de a LSTM vencer.
- **SM5 — Backtest:** ≥ 1 tendência conhecida detectada (Trend Score/surpresa sobem após o surto), documentada qualitativamente.
- **SM6 — Demo:** dashboard sobe offline a partir dos artefatos pré-computados, sem coleta ao vivo, em < 2 min de setup.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-06-08 | 1.0 | Criação inicial do PRD a partir do brief (modo YOLO) | Morgan (@pm) |
| 2026-06-09 | 1.1 | Validação via pm-checklist: + Success Metrics (SM1–SM6), + NFR8 (performance dashboard), + seção Out of Scope, Checklist Results preenchido | Morgan (@pm) |

---

## Requirements

### Functional

- **FR1:** O sistema coleta artigos datados de portais de tecnologia via sitemap, capturando `data`, `título`, `texto`, `fonte`, `categoria` e `url`.
- **FR2:** O sistema persiste um **dataset congelado** (CSV/Parquet) reprodutível para desenvolvimento e demo offline, com deduplicação.
- **FR3:** O sistema limpa e normaliza o texto em português (remoção de URLs/ruído, tratamento de emojis, adequação ao PT informal/técnico).
- **FR4:** O sistema gera **embeddings semânticos** dos artigos usando Sentence-Transformers (PT/multilíngue).
- **FR5:** O sistema agrupa artigos em **tópicos não supervisionados** (UMAP → HDBSCAN) e **nomeia cada tópico automaticamente** via c-TF-IDF.
- **FR6:** O sistema constrói **séries temporais de frequência por tópico**, com granularidade diária (agregação semanal para tópicos esparsos).
- **FR7:** O sistema calcula o **Trend Score estatístico (Camada 1)** — `log(1+recente)·log(crescimento) + λ·max(0,z)` — e ranqueia os "Tópicos em Ascensão". **[MUST]**
- **FR8:** O sistema prevê a frequência futura de tópicos via **LSTM e baseline**, e calcula o **score de surpresa (Camada 2)** — `(real−previsto)/σ_resíduo`. **[SHOULD]**
- **FR9:** O sistema **sinaliza visualmente** tópicos anômalos/sinais fortes (surpresa acima do limiar).
- **FR10:** O dashboard exibe: lista de Tópicos em Ascensão com taxa de crescimento, grafo de co-ocorrência de termos e alertas visuais.
- **FR11:** O dashboard permite filtrar por categoria e janela temporal. **[COULD]**

### Non Functional

- **NFR1:** Stack 100% gratuita/open-source (orçamento zero).
- **NFR2:** O pipeline roda em **GPU local**; geração de embeddings em batch em tempo viável.
- **NFR3:** O **demo é reprodutível offline** a partir do dataset congelado — não depende de coleta ao vivo durante a apresentação.
- **NFR4:** A coleta **respeita `robots.txt` e ToS**, aplica rate-limit (~1 req/s) e **não armazena PII** (conformidade LGPD).
- **NFR5:** Código **modular por fase** (`coleta`, `pln`, `modelagem`, `dashboard`), versionado e documentado.
- **NFR6:** A previsão LSTM é **sempre avaliada contra um baseline** (MAE/RMSE reportados em hold-out) — honestidade científica sobre o resultado.
- **NFR7:** O MVP deve ser **entregável em 2 semanas**, respeitando a priorização MUST > SHOULD > COULD.
- **NFR8:** O dashboard, lendo os artefatos pré-computados, deve **carregar a tela principal em < 5 s** e responder a drill-down/filtros em < 2 s sobre o dataset congelado (percepção de ferramenta real na apresentação).

---

## Out of Scope (MVP) & Future Enhancements

Fronteiras explícitas para proteger o prazo de 2 semanas:

**Fora de escopo no MVP:**
- **Coleta ao vivo durante a apresentação** — o demo roda sobre o dataset congelado (NFR3).
- **Tempo real / streaming** — pipeline é batch offline; nada de ingestão contínua.
- **Twitter/X e redes sociais** — descartado (API paga em 2026); fonte = sitemaps de portais.
- **Autenticação, multiusuário e persistência de sessão** — dashboard read-only público.
- **Acessibilidade formal (WCAG)** — registrada como melhoria futura, não MVP.
- **Deploy em nuvem / CI-CD de produção** — execução local em GPU; sem infra distribuída.
- **Multilíngue além de PT-BR** — corpus focado em português.

**Melhorias futuras (pós-banca):**
- Coleta incremental agendada + alertas por e-mail/Slack de novos sinais fortes.
- Expansão de fontes (mais portais, GDELT pleno, newsletters).
- LSTM multivariada / atenção e re-treino periódico.
- Acessibilidade WCAG AA e internacionalização.
- API pública para consumo do Trend Score por terceiros.

---

## User Interface Design Goals

### Overall UX Vision

Um painel **direto e legível** que, em < 1 minuto, mostra "o que está em alta agora" no setor tech. Foco em clareza informacional, não em sofisticação visual — parecer uma ferramenta real de inteligência, simples e confiável.

### Key Interaction Paradigms

- Visualização primária read-only (dashboard de leitura).
- Filtros leves (categoria, janela temporal) — COULD.
- Drill-down: clicar num tópico em ascensão revela seus artigos representativos e a série temporal.

### Core Screens and Views

- **Painel Principal** — lista ranqueada de "Tópicos em Ascensão" + taxa de crescimento.
- **Detalhe do Tópico** — série temporal, termos representativos (c-TF-IDF), artigos-fonte.
- **Grafo de Co-ocorrência** — termos conectados ao longo do tempo (NetworkX/Plotly).
- **Alertas** — destaque visual de sinais fortes/anomalias.

### Accessibility: None

MVP acadêmico; acessibilidade formal fora de escopo (mencionar como melhoria futura).

### Branding

Mínimo. Tema limpo do Streamlit; identidade visual simples "SONAR". Sem guia de marca obrigatório.

### Target Device and Platforms: Web Responsive

Web via Streamlit, otimizado para desktop (contexto de apresentação na banca).

---

## Technical Assumptions

### Repository Structure: Monorepo

Um único repositório com módulos por fase do pipeline (`src/coleta`, `src/pln`, `src/modelagem`, `src/dashboard`, `dados/`). Simples e adequado ao tamanho do time/prazo.

### Service Architecture

**Monólito em batch + app de visualização.** O pipeline roda em batch (offline) gerando artefatos pré-computados (embeddings, tópicos, séries, scores); o dashboard Streamlit lê esses artefatos. Sem serviços distribuídos, sem tempo real no MVP.

### Testing Requirements

**Unit Only (leve) + validação manual.** Dada a janela de 2 semanas: testes unitários nas funções críticas e determinísticas (parser de sitemap, cálculo do Trend Score, construção de séries) + validação manual/visual do clustering e do dashboard. Backtest qualitativo como teste de aceitação do produto.

### Additional Technical Assumptions and Requests

- **Linguagem:** Python 3.12.
- **PLN/Embeddings:** Sentence-Transformers (modelo PT/multilíngue), Hugging Face Transformers, PyTorch.
- **Topic modeling:** **BERTopic** (UMAP + HDBSCAN + c-TF-IDF) para acelerar — não reimplementar do zero.
- **Coleta:** `requests`/`urllib` + parse de sitemap (stdlib/`lxml`), `trafilatura` para extração de texto.
- **Séries/DL:** `pandas`, PyTorch (LSTM); baseline com `statsmodels`/numpy.
- **Dashboard:** Streamlit + Plotly + NetworkX.
- **Fonte primária:** sitemap do Olhar Digital; secundária: Canaltech; complementar: GDELT (rate-limited).
- **Dataset congelado** versionado para reprodutibilidade do demo.

---

## Epic List

1. **Epic 1 — Fundação & Coleta de Dados:** estabelecer a estrutura do projeto e entregar o dataset congelado de notícias datadas (a matéria-prima de tudo).
2. **Epic 2 — PLN & Modelagem de Tópicos:** transformar o corpus em tópicos nomeados automaticamente via embeddings + clustering.
3. **Epic 3 — Trend Score & Análise Temporal:** construir séries temporais por tópico e calcular o Trend Score (Camada 1 estatística + Camada 2 LSTM).
4. **Epic 4 — Dashboard & Apresentação:** entregar o produto visual (Streamlit) e o estudo de caso com validação por backtest.

> **Rationale (4 epics):** cada epic é um incremento entregável e mapeia tanto as 4 fases do pipeline quanto a divisão natural entre os 4 integrantes (trabalho parcialmente paralelizável após o Epic 1). Cross-cutting (logging, reprodutibilidade, ética) flui dentro das stories, não como epic final.

---

## Epic 1 — Fundação & Coleta de Dados

**Objetivo:** montar o esqueleto do repositório e o pipeline de coleta via sitemap, entregando um dataset congelado, datado e reprodutível — a base sobre a qual todo o resto opera. Já entrega valor verificável (corpus pronto + smoke test).

### Story 1.1 — Setup do projeto e estrutura
Como **equipe de desenvolvimento**, quero **a estrutura do repositório e ambiente configurados**, para que **todos trabalhem com a mesma base modular e reprodutível**.

#### Acceptance Criteria
1: Repositório com pastas `src/{coleta,pln,modelagem,dashboard}`, `dados/`, `docs/`, `tests/`.
2: `requirements.txt`/`environment.yml` com as dependências do MVP; ambiente instala sem erro.
3: Um script/`README` de smoke test roda e confirma que o ambiente (incl. GPU) está funcional.
4: `.gitignore` exclui `dados/` pesado e artefatos; `git init` realizado (via `*environment-bootstrap`).

### Story 1.2 — Coletor de sitemap (URLs datadas)
Como **analista de dados**, quero **listar as URLs de artigos datadas a partir do sitemap dos portais**, para que **eu tenha o índice histórico do corpus sem depender de RSS**.

#### Acceptance Criteria
1: Função lê o sitemap index do Olhar Digital e seleciona sitemaps dos últimos N meses (parametrizável).
2: Extrai `url`, `data` e `categoria` de cada artigo (data/categoria derivadas da URL), com deduplicação.
3: Filtro opcional por categoria; saída em estrutura tabular.
4: Validado sobre ≥ 4 meses, produzindo ≥ 4.000 URLs datadas. *(PoC já provou 2.271 em 2 meses)*

### Story 1.3 — Extração de texto e dataset congelado
Como **analista de dados**, quero **raspar o texto limpo de cada artigo e salvar o dataset**, para que **o corpus fique pronto e reprodutível offline**.

#### Acceptance Criteria
1: Extração de `título` e `texto` com `trafilatura`, respeitando rate-limit (~1 req/s) e `robots.txt`.
2: Falhas de extração são logadas e não interrompem o lote.
3: Dataset salvo em CSV/Parquet com `data, titulo, texto, fonte, categoria, url`, deduplicado.
4: Dataset congelado versionado/documentado para uso pelas fases seguintes (demo offline).

### Story 1.4 — Segunda fonte (Canaltech) [COULD]
Como **analista de dados**, quero **incluir o Canaltech via sitemap**, para que **o corpus seja multi-fonte e as tendências sejam validadas entre portais**.

#### Acceptance Criteria
1: Coletor lê o sitemap do Canaltech (`static.canaltech.com.br/smap/geral.xml`).
2: Artigos normalizados ao mesmo schema e mesclados ao dataset com `fonte` correta.
3: Sem duplicatas entre fontes.

---

## Epic 2 — PLN & Modelagem de Tópicos

**Objetivo:** converter o corpus bruto em tópicos legíveis e nomeados automaticamente, aplicando limpeza, embeddings semânticos e clustering não supervisionado. Entrega o "mapa de assuntos" que alimenta a análise temporal.

### Story 2.1 — Limpeza e normalização PT-BR
Como **engenheiro de PLN**, quero **limpar e normalizar o texto dos artigos**, para que **os embeddings capturem significado e não ruído**.

#### Acceptance Criteria
1: Remoção de URLs, tags HTML residuais e ruído; tratamento de emojis (remoção ou conversão em texto).
2: Normalização adequada ao português (case, espaços, pontuação).
3: Função idempotente e testada em amostra; documentos vazios/curtos são filtrados.

### Story 2.2 — Geração de embeddings
Como **engenheiro de PLN**, quero **gerar embeddings semânticos dos artigos na GPU**, para que **textos com significado próximo fiquem próximos no espaço vetorial**.

#### Acceptance Criteria
1: Embeddings gerados com Sentence-Transformers (modelo PT/multilíngue) usando a GPU local.
2: Processamento em batch; embeddings persistidos para reuso (evita recomputar).
3: Tempo de execução sobre o corpus completo registrado e viável.

### Story 2.3 — Clustering e nomeação de tópicos
Como **cientista de dados**, quero **agrupar os artigos em tópicos e nomeá-los automaticamente**, para que **cada cluster seja um assunto legível, não um número**.

#### Acceptance Criteria
1: Pipeline UMAP → HDBSCAN (via BERTopic) gera clusters; outliers (-1) tratados.
2: c-TF-IDF extrai os termos representativos de cada tópico (rótulo automático).
3: Parâmetros documentados; ≥ 70% dos tópicos avaliados manualmente julgados coerentes.

### Story 2.4 — Atribuição de tópico por documento
Como **cientista de dados**, quero **persistir o tópico atribuído a cada artigo com sua data**, para que **a fase temporal possa montar as séries**.

#### Acceptance Criteria
1: Cada documento recebe `topic_id` (ou -1) e mantém sua `data`.
2: Tabela tópico↔termos↔documentos persistida.
3: Saída validada (contagens por tópico conferem com o total do corpus).

---

## Epic 3 — Trend Score & Análise Temporal

**Objetivo:** medir o crescimento de cada tópico no tempo e produzir o Trend Score de 2 camadas — o coração analítico do produto. Camada 1 (estatística) é must-have; Camada 2 (LSTM) é o diferencial de deep learning.

### Story 3.1 — Séries temporais por tópico
Como **cientista de dados**, quero **montar a série de frequência diária de cada tópico**, para que **o crescimento possa ser medido**.

#### Acceptance Criteria
1: Para cada tópico, série de contagem por dia no período do corpus.
2: Agregação semanal disponível para tópicos esparsos.
3: Séries persistidas; tratamento de dias sem menção (zero-fill).

### Story 3.2 — Trend Score Camada 1 (estatístico) [MUST]
Como **usuário de inteligência de tendências**, quero **um score que ranqueie tópicos em ascensão**, para que **eu veja o que está crescendo de verdade**.

#### Acceptance Criteria
1: Implementa `TrendScore = log(1+R)·log(growth) + λ·max(0,z)` conforme `docs/design/trend-score.md`.
2: Guardas aplicadas: suporte mínimo `n_min`, suavização `α`, tópico novo sinalizado.
3: Parâmetros configuráveis com defaults documentados; função testada unitariamente.
4: Produz ranking de "Tópicos em Ascensão" consumível pelo dashboard.

### Story 3.3 — Previsão LSTM e score de surpresa Camada 2 [SHOULD]
Como **usuário de inteligência de tendências**, quero **detectar tópicos que crescem além do previsto**, para que **eu seja alertado de sinais fortes/anomalias**.

#### Acceptance Criteria
1: Baseline (persistência/média móvel/seasonal-naive) implementado e avaliado (MAE/RMSE em hold-out).
2: LSTM univariada treinada e avaliada **contra o baseline**, com resultados reportados honestamente.
3: `surprise_z = (real−previsto)/σ_resíduo` calculado; alerta quando `> k` (default 2.5).
4: Limitações documentadas (séries curtas etc.).

### Story 3.4 — Validação por backtest
Como **avaliador (banca)**, quero **ver o sistema acertar uma tendência conhecida**, para que **eu confie na detecção**.

#### Acceptance Criteria
1: Seleção de ≥ 1 tendência conhecida presente no corpus (ex.: lançamento de modelo de IA).
2: Pipeline rodado com `T` fixado antes do surto; Trend Score/surpresa do tópico sobem depois.
3: Resultado documentado qualitativamente (acertos e limites).

---

## Epic 4 — Dashboard & Apresentação

**Objetivo:** empacotar tudo num produto visual que pareça uma ferramenta real e numa narrativa de estudo de caso pronta para a banca, incluindo a discussão de ética/LGPD.

### Story 4.1 — Dashboard base e Tópicos em Ascensão
Como **usuário**, quero **um painel com os tópicos em ascensão e sua taxa de crescimento**, para que **eu entenda as tendências em < 1 minuto**.

#### Acceptance Criteria
1: App Streamlit lê os artefatos pré-computados (offline) e sobe sem erro.
2: Lista ranqueada de Tópicos em Ascensão com nome legível e taxa de crescimento.
3: Drill-down do tópico: série temporal + termos representativos + artigos-fonte.

### Story 4.2 — Grafo de co-ocorrência
Como **usuário**, quero **ver como os termos se conectam ao longo do tempo**, para que **eu visualize a estrutura das tendências**.

#### Acceptance Criteria
1: Grafo de co-ocorrência de termos (NetworkX) renderizado no dashboard (Plotly).
2: Legível e responsivo sobre o dataset congelado.

### Story 4.3 — Alertas visuais de anomalia [depende de 3.3]
Como **usuário**, quero **destaque visual para sinais fortes/anomalias**, para que **eu não perca tópicos atípicos emergentes**.

#### Acceptance Criteria
1: Tópicos com `surprise_z > k` recebem alerta visual no painel.
2: Estado gracioso quando a Camada 2 não está disponível (degrada sem quebrar).

### Story 4.4 — Estudo de caso e ética/LGPD
Como **avaliador (banca)**, quero **uma narrativa de caso real e a discussão ética**, para que **o projeto demonstre aplicação e responsabilidade**.

#### Acceptance Criteria
1: Documento/slide de estudo de caso de uma tendência detectada, com explicação do "porquê".
2: Seção de ética: uso de dados públicos, conformidade LGPD, anonimização, risco de alarme falso.
3: README final com instruções de reprodução do demo offline.

---

## Checklist Results Report

> **Executado:** `pm-checklist` (modo comprehensive) — 2026-06-09 por Morgan (@pm).

**Sumário executivo:** Completude geral **~90%** (após quick-wins v1.1) · Escopo MVP **Just Right** · **READY FOR ARCHITECT** · Sem blockers.

| Categoria | Status | Observação |
|---|---|---|
| 1. Problem Definition & Context | 🟢 PASS | Success Metrics SM1–SM6 adicionados; personas em nível adequado ao contexto acadêmico |
| 2. MVP Scope Definition | 🟢 PASS | Seção Out of Scope / Future Enhancements adicionada |
| 3. UX Requirements | 🟢 PASS | NFR8 (performance dashboard) adicionado; journeys cobertos em Core Screens + drill-down |
| 4. Functional Requirements | 🟢 PASS | FR1–FR11 rastreáveis, testáveis e priorizados (MUST/SHOULD/COULD) |
| 5. Non-Functional Requirements | 🟢 PASS | NFR1–NFR8; performance, LGPD/robots e baseline obrigatório cobertos |
| 6. Epic & Story Structure | 🟢 PASS | Epic 1 com setup/scaffolding/smoke test/git; stories como vertical slices |
| 7. Technical Guidance | 🟢 PASS | Constraints, trade-offs e risco LSTM sinalizados para deep-dive do @architect |
| 8. Cross-Functional Requirements | 🟢 PASS | Schema de dados e integrações (sitemaps/GDELT) definidos; monitoramento leve (ok p/ contexto) |
| 9. Clarity & Communication | 🟡 PARTIAL | Diagrama de pipeline pendente — delegado ao @architect (escopo dele) |

**Top issues remanescentes:** nenhum BLOCKER/HIGH. LOW: diagrama de arquitetura (coberto pela fase de arquitetura).

**Decisão final:** ✅ **READY FOR ARCHITECT** — handoff recomendado para @architect (arquitetura + ADR do Trend Score) e, em paralelo, @sm/@po para quebra e validação de stories do Epic 1.

---

## Next Steps

### UX Expert Prompt
@ux-design-expert (Uma): com base neste PRD, projete o layout do dashboard Streamlit do SONAR — Painel Principal (Tópicos em Ascensão), Detalhe do Tópico, Grafo de co-ocorrência e Alertas. Foco em clareza informacional e leitura em < 1 min. Plataforma web/desktop, branding mínimo.

### Architect Prompt
@architect (Aria): com base neste PRD e em `docs/design/trend-score.md`, defina a arquitetura técnica do pipeline batch (coleta → PLN → modelagem → temporal → dashboard), registre o Trend Score de 2 camadas como ADR, especifique os artefatos intermediários (embeddings, tópicos, séries, scores) e o contrato entre fases. Respeite as restrições: monorepo, monólito batch, GPU local, 2 semanas, demo offline reprodutível.
