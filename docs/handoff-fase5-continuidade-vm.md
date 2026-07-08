# Handoff persistente — Continuidade da Fase 5 na VM (GPU)

> **Por que este arquivo existe:** os handoffs de runtime do AIOX ficam em `.aiox/handoffs/`, que é **gitignored** e **não viaja** entre máquinas. Este documento é a versão **committada** do handoff, para a sessão na **VM com GPU** retomar o trabalho lendo um único arquivo. Leia-o na íntegra ao ativar um agente na VM.

- **Data:** 2026-07-08
- **De:** sessão MacBook M1 (planejamento — @architect/@analyst/@sm/@po)
- **Para:** sessão VM com GPU 16GB VRAM (implementação — @devops + @dev)
- **Branch:** `feat/fases-2-4-pipeline`
- **Pipeline:** `trendradar-camada-llm`

---

## 1. O que foi decidido nesta sessão (planejamento completo da Fase 5)

Adicionar uma **Camada de IA Generativa (LLM local)** sobre o pipeline TrendRadar já validado, com duas features que compartilham um cliente único:

- **(A) Analista IA (batch):** rótulo semântico + parágrafo "por que sobe" + briefing por tópico. Grava o **contrato A5** (`dados/insight/briefings.parquet`).
- **(B) RAG conversacional (ao vivo):** pergunta em PT-BR → busca nos embeddings existentes → resposta **com citação de fonte**.

**Motivação:** maior impacto de banca (explica, não só descobre), soberania de dados/LGPD (nada sai da VM), stack de IA completa (embeddings → BERTopic → LSTM → **LLM**).

### Decisões fechadas (NÃO reabrir — estão no ADR-002)
1. **Aditiva e reversível:** o core (coleta/pln/modelagem/scores) **não é tocado**. Só adições + 1 painel opcional no dashboard, guardado por flag (padrão `tem_camada2`).
2. **Provider-agnostic:** `src/common/llm.py` fala OpenAI-compatible; Claude API no dev, **Ollama local no demo** — troca de 1 linha no `config.yaml`.
3. **Serving = Ollama. Modelo firmado = `qwen2.5:14b`** (líder PT-BR no Open PT-LLM Leaderboard: 52,25 > Qwen3 46,47). Shortlist alternativa: `qwen3.5:9b`, `gemma3:12b`.
4. **Degradação graciosa obrigatória:** LLM fora ⇒ dashboard segue com labels c-TF-IDF; `chat()` retorna `None` em falha, nunca levanta exceção.
5. **Contrato A5:** `dados/insight/briefings.parquet` `{topic_id, label_llm, why_summary, model_name, generated_at}`, gravado via `src/common/io.py`.

---

## 2. Documentos-fonte (todos committados nesta branch)

| Documento | Conteúdo |
|---|---|
| `docs/architecture/adr-002-camada-llm.md` | **Decisão formal — Status: Aceito.** Contrato A5, cliente LLM, alternativas rejeitadas, parâmetros |
| `docs/architecture/recommended-approach.md` | Desenho de integração acionável (estrutura de arquivos, fluxos, passos) |
| `docs/architecture/project-analysis.md` | Scan do projeto, padrões, ativos reaproveitáveis |
| `docs/research/2026-07-08-benchmark-llm-local/findings.md` | Por que `qwen2.5:14b` (benchmark PT-BR) |
| `docs/research/2026-07-08-benchmark-llm-local/protocolo-empirico.md` | Teste A/B/C (base da Story 5.6) |

---

## 3. Backlog da Fase 5 — 6 stories, todas em `Ready` (validadas GO pelo @po)

| Story | Arquivo | Prio | Dif. | Depende de |
|---|---|---|---|---|
| 5.1 | `docs/stories/5.1.cliente-llm-provider-agnostic.md` | MUST | 🟡 | — (fundação) |
| 5.2 | `docs/stories/5.2.analista-ia-batch.md` | MUST | 🟡 | 5.1 |
| 5.3 | `docs/stories/5.3.painel-analista-ia-dashboard.md` | MUST | 🟢 | 5.2 |
| 5.4 | `docs/stories/5.4.rag-retriever.md` | SHOULD | 🟡 | 5.1 |
| 5.5 | `docs/stories/5.5.rag-responder-chat.md` | SHOULD | 🔴 | 5.1, 5.4 |
| 5.6 | `docs/stories/5.6.harness-benchmark-llm.md` | COULD | 🟡 | 5.1 |

**Ordem de implementação:** 5.1 → 5.2 → 5.3 (núcleo MUST) → 5.4 → 5.5 (RAG) → 5.6 (benchmark, opcional).

**Should-fix registrados na validação (o @dev incorpora, não bloqueiam):**
- 5.1: incluir `timeout_s` em `InsightParams`.
- 5.2: explicitar a coluna de origem do "trecho" do artigo (corpus A1 vs `corpus_clean`).
- 5.4: garantir cache do encoder da pergunta (não recarregar o modelo ST a cada consulta).

---

## 4. Próximos passos NA VM (nesta ordem)

1. **`git pull`** na branch `feat/fases-2-4-pipeline` (traz este handoff + os 11 arquivos de planejamento).
2. **@devops** → provisionar o Ollama:
   ```bash
   # instalar o Ollama na VM (se ainda não instalado) e baixar o modelo firmado
   ollama pull qwen2.5:14b
   ollama serve   # expõe http://localhost:11434/v1 (OpenAI-compatible)
   ```
3. **@dev** → `*develop 5.1` (cliente LLM — a fundação que destrava tudo). Depois 5.2, 5.3, …
4. **@architect** é o `quality_gate` das 6 stories — revisar cada uma ao concluir.

---

## 5. Estado do ambiente (atenção — diferenças M1 × VM)

- **Modelo firmado:** `qwen2.5:14b` (~9-10GB em Q4 — cabe nos 16GB com folga).
- **Torch/CUDA:** no M1 esta sessão usa MPS com `git update-index --skip-worktree` no `pyproject/lock`. **Na VM (NVIDIA), a source `pytorch-cu124` do `pyproject.toml` é a correta** — confirmar que o `poetry install` puxa a wheel CUDA.
- **Nova dependência da Fase 5:** `openai` (cliente OpenAI-compatible; leve, sem CUDA). Será adicionada pela Story 5.1.
- **Artefatos versionados** (corpus A1, topics, scores, embeddings) já estão no repo — a Fase 5 lê deles; **não precisa rodar o pipeline do zero** para desenvolver.

---

## 6. Como retomar na VM (resumo de 30 segundos)

> Branch `feat/fases-2-4-pipeline`. `git pull`. Ler `docs/architecture/adr-002-camada-llm.md` (Aceito) e a Story 5.1. Rodar `ollama pull qwen2.5:14b`. Ativar `@dev` e `*develop 5.1`. Manter `pytest` verde (89+). Toda decisão de arquitetura/modelo já está fechada — o trabalho na VM é **implementar**, não redecidir.

---

## 7. Trilha de agentes desta sessão (auditoria)

`@aiox-master` (Orion, framing) → `@architect` (Aria: análise + ADR-002) → `@analyst` (Atlas: benchmark → `qwen2.5:14b`) → `@sm` (River: 6 stories) → `@po` (Pax: validação GO → Ready) → `@architect` (Aria: ADR-002 → Aceito) → **[commit/push para a VM]**.
