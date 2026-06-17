# Revisão de Conformidade — Fase 2 (Stories 2.1 → 2.4)

## Status

Review — Findings (não aplicado nenhum código)

## Metadados

```
escopo: "Stories 2.1, 2.2, 2.3, 2.4 (PLN + Modelagem)"
revisor: "@dev (Dex)"
data: 2026-06-17
modo: "auditoria de conformidade (read-only, sem alterações)"
fontes_de_verdade:
  - docs/architecture.md (Contratos A1/A2/A3, Coding Standards)
  - docs/stories/2.1.limpeza-normalizacao-ptbr.md
  - docs/stories/2.2.geracao-embeddings.md
  - docs/stories/2.3.clustering-nomeacao-topicos.md
  - docs/stories/2.4.atribuicao-topico-documento.md
artefatos_inspecionados:
  - src/pln/clean.py, src/pln/embed.py, src/pln/run_clean.py
  - src/modelagem/topics.py, src/modelagem/doc_topics.py, src/modelagem/modelagem.py
  - src/common/io.py, src/common/config.py, config/config.yaml
  - tests/test_clean.py
  - dados/processed/*, dados/topics/* (schemas reais via pyarrow)
```

> **Nota:** este documento é um laudo de revisão. Cada achado traz **como resolver**, mas **nenhuma correção foi aplicada** ao código. As instruções servem para a story de remediação.

---

## Veredito geral

O pipeline da Fase 2 **roda e produz artefatos alinhados** (50 documentos de ponta a ponta: `corpus → clean → embeddings → index → topics → doc_topics`), e a **Story 2.2 (embeddings) está bem executada**. Porém:

1. Foi validado sobre uma **amostra reduzida de 50 notícias** — decisão **intencional da equipe** para agilizar os testes da Fase 2 (não é um problema). O ponto em aberto é que o **gate de coerência SM2 sobre o corpus completo** ainda precisa ser executado antes do fechamento.
2. **Diverge dos Contratos de Artefatos** (A2/A3) que a arquitetura declara como "lei".
3. **O código commitado não reproduz os artefatos em disco** — há descasamento entre `clean.py` e o `corpus_clean.parquet` real, e **não existe o runner `src/pln/run.py`** previsto na arquitetura.
4. **Processo de story não seguido:** as 4 stories continuam em `Ready`, checkboxes de tasks desmarcados, `File List` / `Dev Agent Record` / `Change Log` "(a preencher)".

**Conformidade por story:**

| Story | ACs implementados | Conformidade c/ docs | Achado mais grave |
|---|---|---|---|
| **2.1** Limpeza | Parcial | 🔴 | `data` descartada + `test_clean.py` não é teste (F1, F5) |
| **2.2** Embeddings | Sim | 🟢 | Manifesto fora do contrato (F9) |
| **2.3** Clustering | Parcial | 🔴 | Stopwords EN, schema A3 fora do contrato, sem gate SM2 (F2, F3, F4) |
| **2.4** Doc-topics | Sim (lógica) | 🟡 | Depende de `clean.py` que quebra; `test_doc_topics.py` ausente (F1, F5) |

---

## Achados

Severidade: 🔴 Crítico/Alto · 🟡 Médio · 🟢 Baixo

### 🔴 F1 — Pipeline não-reproduzível: `clean.py` descarta `data` e não há runner

- **Story:** 2.1 / 2.4 · **Coding Standard violado:** "Contrato de artefato é lei" + Reprodutibilidade.
- **Evidência:**
  - `src/pln/clean.py:49` → `resultado = df_limpo[['doc_id', 'texto_limpo']]` — descarta a coluna `data` (e todas as outras de A1).
  - `src/modelagem/doc_topics.py:40-44` → exige `df_corpus[['doc_id','data']]`. Executar o código como está produz **`KeyError: 'data'`** e quebra a Story 2.4.
  - `corpus_clean.parquet` em disco tem cols `[doc_id, texto_limpo, data]` — ou seja, **foi gerado por outro meio**, não pelo `clean.py` atual.
  - `src/pln/run_clean.py` está **vazio** (0 linhas) e a arquitetura prevê `src/pln/run.py` (`python -m src.pln.run`), que **não existe**.
- **Como resolver:**
  1. Ajustar `aplicar_limpeza_corpus()` para **preservar o schema de A1** e apenas acrescentar `texto_limpo`, conforme contrato A2 (`corpus_clean = schema A1 + texto_limpo, menos linhas filtradas`):
     ```python
     # proposta (não aplicada)
     df = df.copy()
     df['texto_limpo'] = df['texto'].apply(limpar_texto)
     return df.dropna(subset=['texto_limpo']).reset_index(drop=True)
     ```
  2. Criar **`src/pln/run.py`** (nome canônico da arquitetura) que faça o I/O via `io.py`:
     ler `dados/raw/corpus.parquet` → aplicar limpeza → `salvar_parquet(..., 'dados/processed/corpus_clean.parquet')`.
  3. Remover o `run_clean.py` vazio (ver F13).
  4. Regerar `corpus_clean.parquet` a partir do código e confirmar que `data` está presente.

---

### 🔴 F2 — Stopwords em inglês num corpus PT-BR

- **Story:** 2.3 · **Viola:** AC2 (rótulo via c-TF-IDF) e o guia ("remoção de stopwords PT no c-TF-IDF").
- **Evidência:** `src/modelagem/topics.py:31` → `CountVectorizer(stop_words="english", ...)`. Confirmado no artefato: top-termos do tópico `-1` em `topic_terms.parquet` são `em`, `que`, `com` (stopwords PT não removidas).
- **Como resolver:**
  - Trocar para stopwords em português no `CountVectorizer`. Ex.: usar lista PT (NLTK `stopwords.words('portuguese')` ou lista própria em `config.yaml`):
    ```python
    # proposta (não aplicada)
    from nltk.corpus import stopwords
    vectorizer_model = CountVectorizer(stop_words=stopwords.words('portuguese'),
                                       ngram_range=(1, 2))
    ```
  - Documentar a fonte da lista de stopwords. Regerar `topic_terms.parquet` / `topic_info.parquet` e reavaliar os rótulos.

---

### 🔴 F3 — Gate SM2 pendente sobre o corpus completo / parâmetros não documentados

- **Story:** 2.3 · **Viola:** AC3 ("parâmetros documentados; ≥70% dos tópicos avaliados manualmente coerentes").
- **Contexto:** a amostra de 50 registros é **intencional** (agilidade de teste) — isto **não** é o achado. O achado é que o gate SM2 sobre o **corpus completo** ainda não foi executado e os parâmetros não estão documentados/justificados.
- **Evidência:** `topics.py:14` usa `min_topic_size=2`, `min_cluster_size=2` hardcoded, sem justificativa registrada. Não há documento de validação manual de coerência nem do % atingido (gate SM2).
- **Como resolver:**
  1. Manter a amostra de 50 para os testes rápidos; antes do fechamento da fase, rodar o clustering sobre o **corpus completo** e tunar `min_topic_size` / `n_neighbors` / `min_cluster_size` com justificativa.
  2. Avaliar manualmente ~20 tópicos, anotar a **% coerente (meta ≥70%)** e os parâmetros usados — na seção `QA Results` da Story 2.3 ou num `docs/qa/coerencia-topicos.md`.
  3. Mover os parâmetros para `config.yaml` (ver F8).

---

### 🔴 F4 — Schema A3 `topic_info` fora do contrato (quebra a jusante)

- **Story:** 2.3 · **Viola:** Contrato A3 (`topic_info = {topic_id, label, size, first_seen_date, last_seen_date}`).
- **Evidência:** `topic_info.parquet` real tem cols `[Topic, Count, Name, Representation, Representative_Docs, first_seen_date, last_seen_date, label]`. As chaves **`topic_id` e `size` não existem** (ficaram com os nomes nativos do BERTopic `Topic`/`Count`). A Story 3.1 lê `topic_info` pelo contrato → risco de quebra.
- **Como resolver:**
  - Renomear/selecionar colunas para o contrato antes de salvar:
    ```python
    # proposta (não aplicada)
    topic_info = topic_info.rename(columns={'Topic': 'topic_id', 'Count': 'size'})
    topic_info = topic_info[['topic_id', 'label', 'size',
                             'first_seen_date', 'last_seen_date']]
    ```
  - Ajustar `doc_topics.py:55` (que hoje lê `df_topic_info['Topic']`) para usar `topic_id`.

---

### 🔴 F5 — Testes exigidos ausentes; `test_clean.py` não é um teste

- **Story:** 2.1 / 2.2 / 2.4 · **Viola:** seção *Testing* de cada story.
- **Evidência:**
  - `tests/test_clean.py` **não testa nada**: é um script que **recria `dados/raw/corpus.parquet`** com 5 notícias fake (`df.to_parquet('dados/raw/corpus.parquet')`) — chega a sobrescrever dados.
  - `tests/test_embeddings_align.py` (sugerido na 2.2) — **ausente**.
  - `tests/test_doc_topics.py` (exigido na 2.4) — **ausente**.
- **Como resolver:**
  1. Mover o gerador de amostra para fora de `tests/` (ex.: `scripts/criar_amostra.py` ou `notebooks/`).
  2. Criar `tests/test_clean.py` real: casos fixos de URL/HTML/emoji/espaços, **idempotência** (`limpar(limpar(t)) == limpar(t)`), filtro de curtos. Ver F-extra sobre idempotência.
  3. Criar `tests/test_embeddings_align.py` (leve, com `encode` mockado): `assert emb.shape[0] == len(corpus_clean)` e unicidade do índice.
  4. Criar `tests/test_doc_topics.py` determinístico: dado `doc→topic` e `doc→data` simulados, validar `doc_topics` e a checagem de contagem (`soma == total`).
  5. Rodar `poetry run pytest` e garantir verde.

---

### 🟡 F6 — Datas `first_seen_date` / `last_seen_date` fabricadas

- **Story:** 2.3 · **Viola:** Contrato A3 (semântica de `first_seen` → badge "novo").
- **Evidência:** `topics.py:117-119` seta `hoje - 7 dias` / `hoje` para **todos** os tópicos, em vez de derivar das datas reais dos documentos do tópico.
- **Como resolver:** calcular a partir das datas reais, fazendo um `groupby('topic_id')` sobre `doc_topics` (com `data`):
  ```python
  # proposta (não aplicada)
  datas = doc_topics.groupby('topic_id')['data'].agg(['min', 'max'])
  topic_info['first_seen_date'] = topic_info['topic_id'].map(datas['min'])
  topic_info['last_seen_date']  = topic_info['topic_id'].map(datas['max'])
  ```

---

### 🟡 F7 — Artefatos A3 no diretório errado

- **Story:** 2.3 · **Viola:** Contrato A3 (artefatos A3 em `dados/topics/`).
- **Evidência:** `topic_info.parquet` e `topic_terms.parquet` foram salvos em `dados/processed/` (`topics.py:128,132`). Só o `doc_topics` final foi para `dados/topics/`. A Story 3.1 procura A3 em `dados/topics/`.
- **Como resolver:** alterar `caminho_saida` de `topics.py` para `dados/topics/` (e manter `doc_id`-alinhamento). Atualizar quem lê esses arquivos.

---

### 🟡 F8 — Config-as-Code / pydantic ignorado (números mágicos)

- **Story:** 2.1-2.4 · **Viola:** Coding Standard "Config centralizada: parâmetros só via objeto pydantic de `config.yaml` — sem número mágico".
- **Evidência:** existe `config/config.yaml`, mas `src/common/config.py` é uma **classe Python simples** que não lê o YAML nem usa pydantic. Números mágicos hardcoded: `batch_size=64`, `min_topic_size=2`, `n_neighbors=15`, `min_cluster_size=2`, `cluster_selection_epsilon=0.1`, limiar `< 10` chars (clean.py:34), `timedelta(days=7)`.
- **Como resolver:**
  1. Implementar `src/common/config.py` com pydantic carregando `config/config.yaml` (modelo tipado).
  2. Adicionar ao `config.yaml` as chaves de PLN/modelagem (ex.: `embedding.batch_size`, `clustering.min_topic_size`, etc.).
  3. Trocar os literais no código por leituras do objeto de config.

---

### 🟡 F9 — Manifesto transversal não usado

- **Story:** 2.2 / 2.3 · **Viola:** Coding Standard "I/O só via `io.py`" + Contrato transversal `dados/run_manifest.json`.
- **Evidência:** `io.py` oferece `atualizar_manifest()` → `dados/run_manifest.json` (schema `{run_id, config_hash, model_name, n_docs, n_topics, stage_versions, params}`). Em vez disso, `embed.py:156` grava `dados/processed/run_manifest.json` (local e schema próprios) e `topics.py:156` grava `topic_manifest.json`.
- **Como resolver:** substituir as gravações ad-hoc por chamadas a `atualizar_manifest(stage="pln"/"modelagem", n_docs=..., n_topics=..., params=...)`. Remover os manifestos duplicados.

---

### 🟡 F10 — `corpus_clean` perde colunas de A1

- **Story:** 2.1 · **Viola:** Contrato A2 (`corpus_clean = schema A1 + texto_limpo`).
- **Evidência:** saída real tem só `[doc_id, texto_limpo, data]`; perde `titulo`, `fonte`, `categoria`, `url`.
- **Como resolver:** resolvido junto com F1 (preservar o DataFrame de A1 e só acrescentar `texto_limpo`).

---

### 🟢 F11 — `label` usa só o 1º termo

- **Story:** 2.3 · **Viola:** Contrato A3 / guia ("`label` = junção dos top termos").
- **Evidência:** `topics.py:122` → `model.get_topic(row['Topic'])[0][0]` (um único termo).
- **Como resolver:** juntar os top-N termos:
  ```python
  # proposta (não aplicada)
  termos = [t for t, _ in model.get_topic(tid)[:3]]
  label = " ".join(termos)
  ```

---

### 🟢 F12 — `doc_topics.py` mascara perda de dados no join

- **Story:** 2.4 · **Viola:** guia ("Datas faltando após o join → algum doc_id não bateu").
- **Evidência:** `doc_topics.py:51` preenche datas ausentes com `pd.Timestamp.now()`, escondendo um join quebrado em vez de falhar/avisar forte.
- **Como resolver:** em vez de `fillna(now())`, **falhar (fail-fast)** ou logar erro claro com os `doc_id` órfãos, conforme Error Handling Strategy ("fail-fast com log claro" nas fases de processamento).

---

### 🟢 F13 — Arquivos mortos (`run_clean.py`, `modelagem.py` vazios)

- **Evidência:** `src/pln/run_clean.py` e `src/modelagem/modelagem.py` têm 0 linhas. Não são exigidos por nenhuma story.
- **Como resolver:** remover ambos (ou popular `modelagem.py`/criar `run.py` se forem virar os runners — ver F1).

---

### 🟡 F14 — Processo de story não seguido

- **Viola:** `story-lifecycle.md` (transições de status, File List, checkboxes).
- **Evidência:** as 4 stories continuam em `Ready`; tasks/subtasks todas `[ ]`; `Dev Agent Record`, `File List` e `Change Log` "(a preencher)".
- **Como resolver:** ao implementar/corrigir, marcar checkboxes concluídos, preencher `File List` (arquivos criados/modificados), registrar no `Change Log` as transições `Ready → InProgress → InReview` e atualizar `Status`.

---

## ✅ O que está correto (mérito)

- **Story 2.2 (embeddings) — a melhor executada:** GPU com fallback CPU, `batch`, `float32`, shape real `(50, 768)` = mpnet D=768, **índice salvo no mesmo passo** e **asserts de alinhamento** (`embed.py:132-133`). AC1/AC2 atendidos.
- **Alinhamento N=50 consistente** em todo o pipeline.
- **BERTopic recebe embeddings pré-computados** (`embedding_model=None`, `embeddings=...`) — não recomputa. Ponto de rigor da 2.3 atendido.
- **UMAP `random_state=42`** fixado (reprodutibilidade).
- **Story 2.4:** join `how="left"`, validação de contagem (`soma == total`) e checagem de `topic_id` válidos — lógica dos 3 ACs implementada.
- **Acentos preservados** na limpeza (`\w` + `re.UNICODE`), como pede a 2.1.
- `src/common/io.py` bem feito (cria diretórios, docstrings, manifesto transversal disponível).

---

## Ordem de remediação sugerida

1. **F1 + F10** — consertar `clean.py` (preservar A1 + `data`) e criar `src/pln/run.py`; regerar `corpus_clean.parquet`.
2. **F2** — stopwords PT no c-TF-IDF; regerar `topic_terms`/`topic_info`.
3. **F4 + F7** — schema A3 de `topic_info` no contrato e artefatos em `dados/topics/`.
4. **F6** — `first_seen`/`last_seen` a partir das datas reais.
5. **F5** — criar os 3 testes; mover o gerador de amostra para fora de `tests/`.
6. **F8 + F9** — ligar `config.py` ao `config.yaml` (pydantic) e usar `atualizar_manifest`.
7. **F3** — rodar sobre corpus real, tunar e documentar coerência (gate SM2).
8. **F11, F12, F13, F14** — ajustes finais e higiene de processo.

---

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2026-06-17 | 1.0 | Laudo de revisão da Fase 2 (14 achados, read-only) | Dex (@dev) |
