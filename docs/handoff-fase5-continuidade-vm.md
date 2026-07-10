# Handoff persistente — Fase 5 IMPLEMENTADA (encerramento da sessão VM)

> **Por que este arquivo existe:** os handoffs de runtime do AIOX ficam em `.aiox/handoffs/` (gitignored, não viajam entre máquinas). Este é o handoff **committado** — a próxima sessão retoma lendo este arquivo na íntegra.

- **Data:** 2026-07-08 (atualizado no encerramento da sessão de implementação)
- **De:** sessão VM GPU 16GB (implementação — @devops/@dev/@architect)
- **Para:** próxima sessão (qualquer máquina; ver §4 para diferenças de ambiente)
- **Branch:** `feat/fases-2-4-pipeline` — ⚠️ **10 commits locais SEM push** (ver §3)
- **Pipeline:** `trendradar-camada-llm`

---

## 1. Estado da Fase 5 — MUST e SHOULD completos ✅

| Story | Título | Status | Gate | Commit |
|---|---|---|---|---|
| 5.1 | Cliente LLM provider-agnostic (`src/common/llm.py`) | **Done** | PASS 8/8 | `429d2c2` |
| 5.2 | Analista IA batch — contrato A5 (`src/insight/`) | **Done** | PASS 8/8 | `04afc77` |
| 5.3 | Painel Analista IA no dashboard | **Done** | PASS 7/7 | `bfa7706` |
| 5.4 | RAG retriever (`src/rag/retriever.py`) | **Done** | PASS 8/8 | `47bf7e0` |
| 5.5 | RAG chat com citação + streaming | **Done** | PASS 7/7 | `8e03b8e` |
| 5.6 | Harness benchmark A/B/C | **Ready** (COULD, opcional — único item restante) | — | — |

**Evidências-chave (registradas nos Dev Agent Records e QA Results das stories):**
- Suíte: **142 testes verdes** (89 herdados + 53 novos da fase). `ruff` limpo nos arquivos novos.
- A5 real gerado: `dados/insight/briefings.parquet` **versionado** (37 tópicos, qwen2.5:14b, 0 fallbacks, 121,5s).
- Anti-alucinação validada com 4 perguntas-pegadinha (2 off-domain + 2 in-domain no gate).
- Streaming real: 1º token em 0,7s. Retriever com encoder cacheado: 0,02s/consulta.
- Degradação graciosa provada AO VIVO em cada elo (`systemctl stop ollama` → tudo segue).

## 2. Como rodar o demo completo

```bash
ollama serve            # se não estiver como serviço (na VM já é systemd, sobe sozinho)
poetry run streamlit run src/dashboard/app.py
# Painéis: ranking com labels LLM + aba "🧠 Análise" + chat "💬 Converse com as Tendências"
# Batch (re)gerar briefings: poetry run python -m src.insight.run
```

## 3. Pendências para a próxima sessão (em ordem)

1. **`@devops *push`** — os 10 commits locais (5 feat + 5 docs/gates) existem SÓ nesta VM. É a pendência nº 1 (recomendação formal da @architect no gate da 5.5).
2. **Identidade git:** os commits saíram com autor auto-gerado (`202473567@senacgoon.local@VDI-...`). Se quiser corrigir: `git config --global user.name/user.email` (+ opcional rebase de autor antes do push).
3. **Story 5.6 (opcional, COULD):** harness A/B/C (`docs/research/2026-07-08-benchmark-llm-local/protocolo-empirico.md`). Carry-forward do gate 5.5: ajuste fino de prompt (artefato cosmético "[1]" após a recusa honesta).
4. **Dívida ruff legada:** 37 apontamentos em módulos pré-Fase 5 (modelagem, dashboard, scores, pln, scripts) — sugerida story de housekeeping (baixa prioridade).
   - Incluir no housekeeping: a suíte de testes (smoke) **escreve no `dados/run_manifest.json` versionado** (poluição: `n_docs` vira 4 e o timestamp muda a cada `pytest`) — idealmente os testes deveriam usar manifesto temporário.
5. **Fechamento formal das stories 1.5–4.4** (estão `InReview` desde antes desta sessão; gates de QA só existem para a Epic 1).

## 4. Estado do ambiente (VM vs outras máquinas)

- **VM (esta máquina):** Ollama v0.31.2 como serviço systemd (habilitado no boot) + `qwen2.5:14b` baixado (9GB, 100% GPU, ~9,6GB/16GB VRAM). Torch 2.6.0+cu124 com CUDA OK. AIOX 5.2.9 instalado (gitignored, local).
- **Artefatos gitignorados regenerados nesta VM** (não viajam): `dados/processed/embeddings.npy` (19MB) e `corpus_clean.parquet`. Em outra máquina, regenerar com:
  ```bash
  poetry run python -c "
  from pathlib import Path
  from src.common.io import ler_parquet, salvar_parquet
  from src.pln.clean import aplicar_limpeza_corpus
  salvar_parquet(aplicar_limpeza_corpus(ler_parquet('dados/raw/corpus.parquet')), Path('dados/processed/corpus_clean.parquet'))"
  poetry run python -c "from src.pln.embed import embed_corpus; embed_corpus()"   # 13,5s na GPU
  ```
  ⚠️ **NÃO rodar o clustering/topics** — os artefatos de tópicos versionados são a referência do A5/scores.
- **Sem LLM na máquina?** Sem problema: o dashboard degrada graciosamente (labels c-TF-IDF, chat some) e o A5 versionado mantém o painel Analista IA funcionando.
- **CodeRabbit CLI:** não instalado na VM — skip gracioso conforme config (validação por revisão manual, padrão do projeto).

## 5. Decisões técnicas tomadas nesta sessão (não reabrir sem motivo)

1. `timeout_s=120s` no `InsightParams` (cold start do Ollama ~59s medido) + `api_key_env` (chave via env var, dummy "ollama").
2. `trecho_max_chars=500` na config (truncamento de trecho não podia ser número mágico).
3. Analista IA: **2 chamadas por tópico** (rotulação + why) em vez de JSON single-call — parsing robusto com 14B local. Trecho vem do **corpus A1 `texto`** (não `corpus_clean`) — should-fix @po resolvido.
4. Curto-circuito no batch: 1ª falha total sem sucesso anterior ⇒ fallback direto nos demais (evita 74 timeouts).
5. `src/dashboard/insight.py` como módulo (precedente `graph.py`) — aprovado no gate 5.3.
6. `chat_stream()` e `llm_disponivel()` (ping 3s de UI) adicionados ao `llm.py` — extensão aditiva da 5.1.
7. Recusa honesta do RAG **sem chamar o LLM** quando o retriever volta vazio.

## 6. Como retomar (resumo de 30 segundos)

> Branch `feat/fases-2-4-pipeline`. Ler este arquivo. **1º passo: `@devops *push`** (10 commits locais). Depois: 5.6 opcional (`@dev *develop 5.6`) ou fechamento das stories 1.5–4.4. Demo: `poetry run streamlit run src/dashboard/app.py`. Suíte deve permanecer em **142 verdes** (`poetry run pytest`).

## 7. Trilha de agentes desta sessão (auditoria)

`@aiox-master` (Orion: instalação AIOX + mapeamento do projeto) → `@devops` (Gage: Ollama + qwen2.5:14b provisionados) → ciclo ×5 [`@dev` (Dex: implementação) → `@architect` (Aria: quality gate PASS)] para as stories 5.1→5.5 → **[este handoff]**.
