# ADR-002 — Camada de IA Generativa (LLM local)

- **Status:** Aceito
- **Data:** 2026-07-08 (proposto) · 2026-07-08 (aceito)
- **Decisores:** @architect (Aria, registro) · owner do projeto (decisões de design elicitadas) · @analyst (Atlas, benchmark de modelo — concluído) · @po (Pax, 6 stories validadas GO)
- **Fonte:** `docs/architecture/project-analysis.md`, `docs/architecture/recommended-approach.md`, `docs/research/2026-07-08-benchmark-llm-local/findings.md`
- **Relacionado:** `docs/architecture/adr-001-trend-score.md` (padrão de degradação graciosa), `docs/estudo-de-caso-etica-lgpd.md` (soberania de dados), `src/dashboard/app.py` (precompute-then-serve)

---

## Contexto

O SONAR **descobre** e **quantifica** tendências muito bem (BERTopic + Trend Score de 2 camadas), mas tem um ponto cego: **não as explica em linguagem humana**. O dashboard entrega listas de termos c-TF-IDF (ex.: `iphone apple`) e curvas — o usuário precisa interpretar sozinho. É exatamente aqui que o Google Trends também falha (dá curva, não explicação), e onde uma camada de IA generativa gera maior retorno de produto e de apresentação.

Três forças moldam a decisão:

1. **Valor de produto e de banca:** transformar tópicos crus em *narrativa* ("por que está subindo") e permitir *perguntar* às tendências é o salto mais visível — e diferencia do Google Trends.
2. **Hardware disponível:** a equipe tem uma VM com GPU de **16GB VRAM**, suficiente para um LLM local robusto (teto ~14B em 4-bit) nas tarefas pretendidas — que são *grounded* (o modelo recebe os artigos, não precisa de conhecimento de mundo).
3. **Restrição de integridade:** o pipeline já está validado (89 testes, gate SM2 PASS). A nova camada **não pode arriscar** o core — precisa ser aditiva e reversível.

## Decisão

Adicionar uma **camada de IA generativa servida por LLM local**, composta por duas features que compartilham um único cliente agnóstico ao provedor, seguindo o padrão *precompute-then-serve + degradação graciosa* já consagrado pela Camada 2 (ADR-001).

### Feature A — Analista IA (batch, offline)

Novo estágio de pipeline (`src/insight/`) que roda **após** os scores e, para cada tópico em ascensão:
- seleciona os artigos representativos (`doc_topics` × `corpus`);
- gera via LLM um **nome semântico** e um parágrafo **"por que está subindo"**;
- persiste o **contrato A5** (`dados/insight/briefings.parquet`).

Determinístico por convenção (`temperature=0`); o dashboard lê o artefato e exibe os rótulos/narrativas no lugar dos termos crus.

### Feature B — RAG conversacional (online, no dashboard)

Módulo `src/rag/` + painel de chat no `app.py`:
- embeda a pergunta (mesmo modelo Sentence-Transformers já usado) e faz **similaridade de cosseno sobre `embeddings.npy`** (reúso — a matriz de 6.423 artigos já está persistida);
- monta um prompt restritivo ("responda **só** com base nestes trechos") e retorna a resposta **com citação dos artigos-fonte**.

### Contrato do cliente LLM (decisão central — provider-agnostic)

`src/common/llm.py` expõe **uma** interface OpenAI-compatible, dirigida por config:

```python
def chat(messages, *, temperature, max_tokens) -> str | None:
    """Retorna None em falha → degradação graciosa (o dashboard segue com c-TF-IDF)."""
```

- **Dev / iteração de prompt:** `base_url` → Claude API (rápido).
- **Demo / banca:** `base_url` → **Ollama** local (`http://localhost:11434/v1`), 100% offline.
- Trocar um pelo outro é **uma linha no `config.yaml`** — nenhuma reescrita.

**Serving escolhido: Ollama** (simplicidade; sobe o modelo em 1 comando, quantização Q4 automática, endpoint OpenAI-compatible pronto).

**Modelo firmado: `qwen2.5:14b` (Qwen2.5-14B-Instruct).** Decidido por pesquisa (@analyst, `findings.md`): no Open PT-LLM Leaderboard o Qwen2.5 lidera em português (52,25), **acima do Qwen3 (46,47)** — no domínio PT-BR, "o mais novo" não é o melhor. É o único da shortlist com evidência pública *direta* de liderança em PT-BR. Shortlist avaliada (o modelo é parametrizado; trocar é 1 linha no YAML):

| Modelo | Ollama | VRAM (4-bit) | Papel |
|---|---|---|---|
| **Qwen2.5-14B-Instruct** | `qwen2.5:14b` | ~9-10GB | **default firmado** — líder PT-BR comprovado |
| Qwen3.5-9B | `qwen3.5:9b` | ~6-7GB | desafiante moderno (256K contexto, ótimo p/ RAG) |
| Gemma 3-12B-it | `gemma3:12b` | ~9-10GB | alternativa (140 línguas, saída estruturada) |

Validação empírica no corpus real (A/B/C) fica como **opcional, não-bloqueante** (ver `docs/research/2026-07-08-benchmark-llm-local/protocolo-empirico.md`): as tarefas são *grounded*, o que aproxima 9B de 14B; se o teste indicar outro vencedor, basta trocar `insight.model`.

## Consequências

**Positivas**
- ✅ **Aditiva e reversível:** o core (coleta/pln/modelagem/scores) **não é tocado**; só há novos módulos + 1 painel opcional. Se a camada some, o produto validado continua igual.
- ✅ **Reúso forte (IDS):** o RAG usa `embeddings.npy` já persistido — a parte cara (embeddar o corpus) está feita; nenhum recomputo.
- ✅ **Soberania de dados / LGPD:** LLM local ⇒ nenhum dado editorial sai da VM. **Reforça** a narrativa de ética já existente — poucos projetos de curso fecham esse loop.
- ✅ **Stack completa e coesa:** embeddings PT → BERTopic → LSTM → **LLM**, tudo self-hosted. Narrativa de banca: *"ML clássico descobre e mede; IA generativa explica e conversa."*
- ✅ **Degradação graciosa codificável:** flags `tem_insight` / `tem_rag` no dashboard (espelham `tem_camada2`).

**Negativas / custos**
- ⚠️ Não-determinismo do LLM tensiona a reprodutibilidade. **Mitigação:** `temperature=0` no batch; registrar `model_name` no A5 e no `run_manifest.json`.
- ⚠️ Risco de alucinação no RAG. **Mitigação:** prompt restritivo aos trechos recuperados + citação sempre visível + `temperature` baixa.
- ⚠️ Latência do 14B no chat ao vivo. **Mitigação:** streaming de resposta; Analista IA em batch (não ao vivo); Gemma-2-9B como opção mais leve.
- ⚠️ Dependência da VM no demo. **Mitigação:** pré-gerar e versionar `briefings.parquet` (fallback estático, como os outros artefatos leves).

## Alternativas rejeitadas

| Alternativa | Por que rejeitada |
|---|---|
| **Só Claude API (sem LLM local)** | Perde a soberania de dados/LGPD e desperdiça a GPU disponível; cria dependência externa e custo por chamada no demo. Mantida apenas como caminho de *dev* via o mesmo cliente. |
| **Modelo local 27-32B** | Não cabe confortável em 16GB VRAM (~18-20GB em 4-bit); forçar Q3 degrada qualidade e contexto. Desnecessário para tarefas grounded. |
| **vLLM em vez de Ollama** | Melhor throughput, mas setup mais trabalhoso (quantização manual) sem ganho relevante para 1 usuário na banca. Reconsiderável se surgir necessidade de escala. |
| **Rotular tópicos com regras/heurística (sem LLM)** | Não entrega narrativa nem "por que sobe"; é o que já existe (c-TF-IDF). |
| **RAG com novo modelo de embeddings** | Ignoraria `embeddings.npy` já pronto; recomputo caro sem ganho — viola REUSE > CREATE. |
| **Fine-tuning de um modelo próprio** | Custo/complexidade incompatíveis com o escopo; RAG resolve o grounding sem treino. |

## Parâmetros (defaults tunáveis — seção `insight:` no `config.yaml`)

| Parâmetro | Default | Papel |
|---|---|---|
| `base_url` | `http://localhost:11434/v1` | endpoint OpenAI-compatible (Ollama local / Claude no dev) |
| `model` | `qwen2.5:14b` | modelo servido; firmado por pesquisa @analyst (líder PT-BR); shortlist alternativa: `qwen3.5:9b`, `gemma3:12b` |
| `temperature_batch` | 0.0 | determinismo do Analista IA (reprodutibilidade) |
| `temperature_chat` | 0.3 | fluidez do RAG |
| `max_tokens` | 512 | teto de geração |
| `rag_top_k` | 6 | nº de trechos recuperados por pergunta |
| `top_artigos` | 5 | artigos representativos por tópico no contexto do batch |

> Como no ADR-001: qualquer ajuste destes defaults deve ser justificado no relatório final — a banca valoriza tuning com **porquê**.

## Implementação

- **Cliente LLM** em `src/common/llm.py` (determinístico via mock nos testes; `None` em falha → degradação graciosa).
- **Analista IA** em `src/insight/` (`run.py` espelha `scores/run.py`; grava A5 via `src/common/io.py`; registra no manifesto).
- **RAG** em `src/rag/` (`retriever.py` = cosseno sobre `embeddings.npy`; `responder.py` = prompt + citação).
- **Dashboard**: extensão pequena e opcional em `src/dashboard/app.py` (painel Analista IA + `st.chat_input`), guardada por flags de disponibilidade.
- **Config**: seção `insight:` + classe `InsightParams` (pydantic), padrão idêntico ao `TrendScoreParams`.
- **Dependência nova:** `openai` (cliente OpenAI-compatible; fala com Ollama e Claude). Sem CUDA, leve.
- **Validação:** manter a suíte pytest verde (89+); testar explicitamente o caminho de degradação graciosa (endpoint off).

> **Pendências antes de `Aceito`:** ~~(1) benchmark de modelo (@analyst) fixando `insight.model`~~ ✅ `qwen2.5:14b` firmado (`findings.md`); ~~(2) quebra em stories da Fase 5 (@sm)~~ ✅ 6 stories (5.1–5.6) criadas e **validadas GO** pelo @po (todas em `Ready`). **Ambas concluídas → ADR ACEITO em 2026-07-08.** Validação empírica A/B/C permanece opcional/não-bloqueante (Story 5.6, COULD).
>
> **Implementação:** rastreada pelas stories `docs/stories/5.1`–`5.6`. Ordem: 5.1 (fundação) → 5.2 → 5.3 (núcleo MUST) → 5.4 → 5.5 (RAG, SHOULD) → 5.6 (benchmark, COULD). Executor @dev, quality gate @architect.
