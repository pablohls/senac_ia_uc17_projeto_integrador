# Project Brief: Mapeador de Tendências em Tecnologia (SONAR)

> **Status:** Draft (YOLO) — gerado por @analyst (Atlas) em 2026-06-08
> **Base:** `docs/briefing.md` + análise de viabilidade
> **Contexto:** Projeto Integrador final — Curso de IA (1200h)
> **Próximo passo:** Handoff para @pm criar o PRD

---

## Executive Summary

**SONAR** é uma ferramenta de inteligência que monitora portais de tecnologia em português, agrupa automaticamente as notícias por assunto e identifica **quais tópicos estão ganhando tração** — sinalizando tendências emergentes antes que elas se tornem óbvias.

- **Conceito:** pipeline de PLN + Deep Learning que transforma um fluxo de notícias (via RSS) em um painel de "tópicos em ascensão" no setor de Tecnologia/Ciência.
- **Problema resolvido:** o volume de publicações sobre tecnologia é grande demais para acompanhamento manual; identificar o que está crescendo exige leitura e intuição que não escalam.
- **Mercado/usuário-alvo:** profissionais que precisam antecipar movimentos do setor tech — analistas de inovação, criadores de conteúdo, product managers — e, no contexto acadêmico, a banca avaliadora como prova de domínio técnico integrado.
- **Proposta de valor:** detecção automática e datada de tendências emergentes, com nomeação automática dos tópicos e alertas visuais, entregue como um produto funcional (dashboard) e não apenas como um experimento.

---

## Problem Statement

**Estado atual e dores:**
O ecossistema de tecnologia produz centenas de notícias por dia em dezenas de portais brasileiros. Profissionais que dependem de antecipar tendências (para conteúdo, produto, investimento ou estratégia) hoje fazem isso **manualmente** — lendo feeds, confiando em intuição e percebendo movimentos só quando já são consenso, ou seja, tarde demais.

**Impacto:**
- Perda de janela competitiva: quem percebe uma tendência depois dos concorrentes perde vantagem de pauta/produto.
- Esforço humano não escala: acompanhar múltiplas fontes consome horas e ainda assim cobre uma fração do que é publicado.
- Viés de percepção: o que "parece" tendência nem sempre é — falta medição objetiva da taxa de crescimento de um assunto.

**Por que as soluções atuais não bastam:**
Ferramentas genéricas (Google Trends) medem busca, não cobertura editorial, e não agrupam temas automaticamente em português técnico. Soluções comerciais de *media monitoring* são caras e fechadas. Falta uma abordagem que **descubra tópicos sozinha** (sem categorias pré-definidas) e **meça crescimento ao longo do tempo** sobre fontes em PT-BR.

**Urgência (contexto do projeto):**
Como projeto integrador, o problema é uma vitrine ideal para integrar as disciplinas do curso (PLN, embeddings, clustering, redes neurais recorrentes) num produto coeso e demonstrável — com prazo de entrega de **2 semanas**.

---

## Proposed Solution

**Conceito central:** um pipeline automatizado em 4 estágios:

1. **Coleta** — ingestão contínua de notícias via RSS de portais de tecnologia (ex.: Olhar Digital, Canaltech), capturando `data`, `título`, `texto` e `fonte`.
2. **PLN** — limpeza/normalização do texto, geração de **embeddings semânticos** (Sentence-Transformers em PT) e, opcionalmente, NER para extrair marcas/produtos/pessoas.
3. **Modelagem** — redução de dimensionalidade (UMAP) → clusterização (HDBSCAN) → nomeação automática dos tópicos (c-TF-IDF); construção de **séries temporais por tópico** (frequência de menções/dia ou semana) e cálculo de um **Trend Score** (crescimento + aceleração + recência). Demonstração de **Deep Learning sequencial (LSTM)** para previsão da frequência futura de um tópico, comparada a um baseline.
4. **Produto** — **dashboard Streamlit** com lista de "Tópicos em Ascensão", grafo de co-ocorrência de termos e alertas visuais.

**Diferenciais:**
- **Descoberta não supervisionada** de tópicos (sem taxonomia manual) — adapta-se a temas novos automaticamente.
- **Nomeação automática** dos clusters via c-TF-IDF — clusters legíveis, não números.
- **Medição objetiva** de tendência (Trend Score) em vez de percepção subjetiva.
- **Foco em PT-BR técnico** — usa modelos treinados/adaptados ao português.

**Por que vai funcionar onde outras não funcionam:** combina o estado da arte de *topic modeling* (pipeline tipo BERTopic) com uma camada temporal explícita e um produto visual — entregando algo que *parece e age como uma ferramenta real*, que é o que diferencia diante da banca.

---

## Target Users

### Primary User Segment: Analista de Inovação / Tendências em Tech

- **Perfil:** profissional de empresa de tecnologia, consultoria ou mídia especializada que precisa reportar "o que está em alta" no setor.
- **Comportamento atual:** acompanha manualmente vários portais e newsletters; compila relatórios periódicos de tendências.
- **Necessidades:** visão consolidada e datada dos assuntos emergentes; evidência objetiva (números) para sustentar recomendações; rapidez.
- **Objetivo:** antecipar tendências para informar decisões de pauta, produto ou estratégia.

### Secondary User Segment: Criador de Conteúdo / Jornalista de Tecnologia

- **Perfil:** produtor de conteúdo (canal, blog, newsletter) que vive de pauta relevante e oportuna.
- **Comportamento atual:** "fareja" assuntos lendo feeds e redes; depende de timing.
- **Necessidades:** identificar pautas em ascensão antes da concorrência; ver quais termos estão se conectando.
- **Objetivo:** publicar sobre o assunto certo no momento certo.

> **Nota acadêmica:** o avaliador real do MVP é a **banca**. O sucesso do projeto se mede tanto pela utilidade simulada para os personas acima quanto pela demonstração de domínio técnico integrado das disciplinas do curso.

---

## Goals & Success Metrics

### Objetivos do Projeto (acadêmico)

- Entregar, em **2 semanas**, um pipeline ponta a ponta funcional (coleta → PLN → modelagem → dashboard) demonstrável ao vivo.
- Integrar de forma explícita ≥ 4 disciplinas do curso: PLN, embeddings/Transformers, clustering não supervisionado e redes neurais (LSTM).
- Produzir um estudo de caso com uma tendência real detectada e explicada.
- Documentar decisões técnicas, incluindo experimentos que falharam e ajustes de rota.

### Métricas de Sucesso do Usuário

- O usuário consegue identificar os 3–5 tópicos em ascensão da semana em < 1 minuto no dashboard.
- Cada tópico tem nome legível (não "cluster 7") e termos representativos coerentes.
- Os alertas correspondem a assuntos que um humano do setor reconheceria como relevantes.

### KPIs (Indicadores)

- **Coerência de tópicos:** ≥ 70% dos tópicos avaliados manualmente são julgados "coerentes" (rótulo bate com o conteúdo). Meta inicial; ajustável.
- **Qualidade da previsão (LSTM):** erro (MAE/RMSE) reportado em janela de teste e **comparado a um baseline simples** (ex.: média móvel/persistência). Sucesso = LSTM documentado e avaliado honestamente, batendo ou não o baseline.
- **Validação de tendência (backtest):** ≥ 1 tendência histórica conhecida corretamente sinalizada pelo sistema em backtesting.
- **Cobertura de dados:** corpus mínimo viável coletado (meta: ver Constraints — histórico suficiente para séries temporais com pelo menos algumas semanas/meses).

---

## MVP Scope

### Core Features (Must Have) — o núcleo demonstrável

- **Coleta via RSS:** ingestão de ≥ 2 portais de tecnologia (Olhar Digital, Canaltech), com deduplicação e persistência de `data, título, texto, fonte`.
- **Pré-processamento PLN:** limpeza (URLs, ruído), normalização para português informal/técnico.
- **Embeddings semânticos:** geração de vetores com **Sentence-Transformers** (modelo multilíngue/PT) — roda em GPU local.
- **Topic modeling:** UMAP → HDBSCAN → c-TF-IDF (recomendado via **BERTopic** para acelerar), com nomeação automática dos tópicos.
- **Série temporal + Trend Score:** frequência de menções por tópico ao longo do tempo e um score de crescimento/aceleração para ranquear "Tópicos em Ascensão".
- **Componente de Deep Learning (LSTM):** previsão da frequência futura de tópico(s) selecionado(s), com avaliação vs. baseline. (Cumpre o requisito de redes neurais recorrentes.)
- **Dashboard Streamlit:** lista de tópicos em ascensão + taxa de crescimento + grafo de co-ocorrência (NetworkX) + alerta visual de tópico atípico.

### Out of Scope for MVP (deixar para depois)

- Múltiplas fontes além de RSS (Reddit, Bluesky, redes sociais).
- Detecção de anomalias com **Autoencoder** (mover para Post-MVP — redundante com outliers do HDBSCAN no curto prazo).
- NER avançado / extração de entidades como feature de produto (opcional; só se sobrar tempo).
- Atualização em tempo real / agendamento automático de coleta em produção.
- Autenticação, multiusuário, deploy hospedado.

### MVP Success Criteria

O MVP é bem-sucedido se, na apresentação, o grupo conseguir: **(1)** rodar o pipeline sobre um dataset congelado (offline, sem depender de coleta ao vivo); **(2)** mostrar no dashboard os tópicos em ascensão com nomes legíveis; **(3)** demonstrar a previsão LSTM com avaliação honesta vs. baseline; e **(4)** apresentar um estudo de caso de uma tendência detectada, com a narrativa do "porquê".

---

## Post-MVP Vision

### Phase 2 Features

- Detecção de sinais fracos via **Autoencoder** (erro de reconstrução para novidade).
- Inclusão de fontes sociais (Reddit/Bluesky) para captar conversa, não só cobertura editorial.
- NER + análise de sentimento por tópico.

### Long-term Vision (1–2 anos)

Uma plataforma de *trend intelligence* multi-domínio (tech, moda, alimentação), com alertas configuráveis, comparação entre fontes e relatórios automáticos periódicos.

### Expansion Opportunities

- Multi-idioma; comparação Brasil vs. tendências globais.
- API para integração com ferramentas de marketing/conteúdo.

---

## Technical Considerations

### Platform Requirements

- **Plataforma-alvo:** aplicação web local (Streamlit) para demo; execução em máquina com **GPU local**.
- **Suporte:** navegador desktop moderno.
- **Performance:** geração de embeddings em batch na GPU; dashboard responsivo sobre dataset pré-processado.

### Technology Preferences

- **Frontend:** Streamlit + Plotly + NetworkX.
- **Backend/Processamento:** Python; PyTorch; Hugging Face Transformers / Sentence-Transformers; BERTopic (UMAP + HDBSCAN + c-TF-IDF); scikit-learn; spaCy (`pt_core_news_lg`) para NER opcional.
- **Coleta:** `feedparser` para RSS (+ `BeautifulSoup`/`requests` se for preciso raspar arquivo histórico dos portais).
- **Armazenamento:** dataset em arquivo (CSV/Parquet) versionado/congelado para reprodutibilidade do demo.

### Architecture Considerations

- **Estrutura do repositório:** módulos separados por estágio do pipeline (coleta, pln, modelagem, dashboard) + pasta de dados.
- **Arquitetura de serviço:** pipeline em batch (não tempo real no MVP); dashboard lê artefatos pré-computados.
- **Integração:** entrada via feeds RSS; possível complemento histórico via arquivo/sitemap dos portais ou GDELT (a pesquisar).
- **Segurança/Conformidade:** dados públicos/editoriais; respeitar ToS dos portais; sem armazenamento de PII; discutir LGPD e riscos de alarme falso na seção de ética.

---

## Constraints & Assumptions

### Constraints

- **Orçamento:** zero (ferramentas gratuitas/open-source).
- **Prazo:** **2 semanas** até a banca — restrição dominante; força priorização agressiva.
- **Recursos:** **4 integrantes**; **1 GPU local**.
- **Técnico:** RSS entrega **janela rolante** (itens recentes), não arquivo histórico completo — limita o tamanho da série temporal sem coleta prévia ou raspagem de arquivo.

### Key Assumptions

- Os feeds RSS escolhidos têm volume diário suficiente para formar clusters com sentido.
- Sentence-Transformers multilíngue/PT dá qualidade de embedding adequada para clustering em português técnico.
- A GPU local comporta a geração de embeddings do corpus em tempo viável.
- Há acesso a histórico suficiente (via coleta acumulada, raspagem de arquivo dos portais, ou dataset externo) para a camada temporal funcionar.
- O grupo consegue dividir o trabalho em 4 frentes paralelas (coleta, PLN/modelagem, DL/temporal, dashboard).

---

## Risks & Open Questions

### Key Risks

- **Histórico insuficiente via RSS:** ~~RSS só traz itens recentes.~~ **✅ RESOLVIDO (ver `docs/research/2026-06-08-backfill-historico/findings.md`).** Confirmado empiricamente que o RSS traz só ~12 itens/dia, mas o **sitemap mensal do Olhar Digital** (`sitemap_post_AAAA-MM.xml`) expõe artigos datados com profundidade de meses/anos (~1.5–2k artigos/mês, data+categoria na URL). Canaltech também tem sitemap (`static.canaltech.com.br/smap/geral.xml`). GDELT (3 meses, pt-BR) como complemento. **Backfill = via sitemap, não RSS.**
- **Prazo de 2 semanas:** **Impacto:** risco de não fechar o ciclo. **Mitigação:** usar BERTopic (não reimplementar do zero), congelar dataset cedo, tratar Autoencoder/NER como opcionais.
- **LSTM com séries curtas:** **Impacto:** overfitting/baixa performance. **Mitigação:** comparar com baseline simples e reportar honestamente; o aprendizado documentado vale mais que o número.
- **Volume de notícias baixo por dia:** **Impacto:** clusters fracos/ruidosos. **Mitigação:** agregar por semana; incluir mais feeds; ajustar parâmetros do HDBSCAN.
- **Demo ao vivo dependente de coleta:** **Impacto:** falha na apresentação. **Mitigação:** rodar sobre dataset congelado offline.

### Open Questions

- Quanto histórico já foi coletado no Colab até agora? Há base para séries de várias semanas/meses?
- Os portais escolhidos permitem raspar artigos antigos datados (arquivo/sitemap)? Quais ToS?
- Qual granularidade temporal (diária vs. semanal) o volume de dados suporta?
- A banca exige obrigatoriamente LSTM/Autoencoder específicos, ou aceita qualquer demonstração robusta de Deep Learning?

### Areas Needing Further Research

- Viabilidade de backfill histórico (raspagem de arquivo dos portais vs. GDELT vs. datasets prontos).
- Melhor modelo de Sentence-Transformers para PT-BR técnico (qualidade vs. custo na GPU local).
- Estratégia de backtesting: qual tendência histórica conhecida usar como "verdade" para validar a detecção.

---

## Appendices

### A. Research Summary

Análise de viabilidade (por @analyst) concluiu que: a fonte original do briefing (Twitter/X) está inviável em 2026 (API paga, sem busca útil no tier grátis); **RSS de portais de tecnologia é a alternativa estável e legal escolhida pelo grupo**; o pipeline descrito equivale a um **BERTopic** (embeddings → UMAP → HDBSCAN → c-TF-IDF), recomendando-se uso da biblioteca para acelerar; e a maior incerteza técnica é a **disponibilidade de histórico temporal**.

### C. References

- `docs/briefing.md` — briefing original do grupo.
- Feeds-alvo: `https://olhardigital.com.br/rss`, `https://feeds.feedburner.com/canaltechbr`.

---

## Next Steps

### Immediate Actions

1. **Decidir o backfill histórico** (raspar arquivo dos portais vs. GDELT vs. dataset) — destrava o risco nº 1.
2. **Congelar um dataset inicial** para desenvolvimento e demo reprodutível.
3. **Montar o esqueleto do pipeline** com BERTopic sobre o dataset congelado (prova de conceito do clustering + nomeação).
4. **Dividir as 4 frentes** entre os integrantes (coleta/backfill, PLN+modelagem, DL/temporal+LSTM, dashboard).
5. **Handoff para @pm** criar o PRD e, em seguida, @sm quebrar em stories.

### PM Handoff

Este Project Brief fornece o contexto completo do **Mapeador de Tendências em Tecnologia (SONAR)**. @pm (Morgan): inicie em 'PRD Generation Mode', revise o brief a fundo e trabalhe com o usuário para criar o PRD seção por seção, pedindo esclarecimentos ou sugerindo melhorias — com atenção especial ao prazo de 2 semanas e ao risco de histórico temporal.
