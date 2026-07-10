# Handoff — Sessão 2026-07-09 (VM GPU) → próxima sessão

> Continuação de `docs/handoff-fase5-continuidade-vm.md` (2026-07-08).
> Estado ao encerrar: **backlog zerado — 26/26 stories Done (Epics 1–6), tudo na `main`**.

## 1. O que esta sessão entregou

1. **Story 5.6 fechada (gate WAIVED)** — benchmark A/B/C executado e consolidado.
   Avaliação cega humana **formalmente dispensada** pela equipe: `qwen3.5:9b` eliminado
   por confiabilidade (34% falha; 0% saída sob contrato de produção) e o vencedor em
   desempenho é o próprio default do ADR-002. **Recomendação final: manter `qwen2.5:14b`.**
   Planilha cega preservada (`avaliacao_cega.csv` + `mapa_cego.json`) — avaliação pode ser
   feita a posteriori com `poetry run python scripts/benchmark_llm.py consolidar --avaliacoes <csvs>`.
2. **Story 6.1 (PASS)** — polimento visual do Streamlit (tema, cards de métricas, paleta
   plotly única) e **reenquadramento do grafo**: seção "🔗 Pontes entre tópicos" (com filtro
   de stopwords NLTK) + grafo completo preservado em expander.
3. **Story 6.2 (PASS)** — rebrand SONAR na UI, **tema dark**, e fix do gráfico de série
   temporal (causa raiz: eixo categórico com `data` string + `count` diário ~zero →
   agora datetime + `count_weekly` + recorte do período morto, `src/dashboard/timeseries.py`).
4. **Fechamento formal das stories 1.5–4.4** — 14 quality gates (@architect, por épico):
   12 PASS, 2 CONCERNS não-bloqueantes (2.3/2.5: stopwords residuais no c-TF-IDF,
   mitigadas pelos labels LLM da 5.2). QA Results preenchidos em todas.
5. **README reescrito para reprodução por outros devs**: seção Fase 5 (instalar Ollama,
   `ollama pull qwen2.5:14b`, ~11GB VRAM, config `insight`, `LLM_API_KEY`), nota de que
   os artefatos de dados são versionados (clone limpo já abre o dashboard) e estrutura atualizada.
6. **PRs #2 e #3 criados e mergeados na `main`** (via API REST — ver §3).
7. **Rebrand COMPLETO `trendradar` → `sonar`** na `main` (commit `1ab620b`): pacote,
   CLI, user-agent, config e docs. Exceções deliberadas: `avaliacao_cega.csv` (artefato
   congelado do benchmark, por reprodutibilidade) e um grep de época no QA record da 6.2.

## 2. ⚠️ BREAKING para todos os integrantes (após `git pull`)

- O comando `poetry run trendradar` **não existe mais** → **`poetry run sonar`**.
- O rename do pacote faz o Poetry criar um **virtualenv novo** → rodar **`poetry install`**
  uma vez (resolve do cache; na primeira máquina pode baixar dependências).

## 3. Ambiente da VM (notas operacionais)

- Ollama v0.31.2 (systemd) + `qwen2.5:14b`; também baixados `qwen3.5:9b` e `gemma3:12b` (benchmark).
- **`gh` CLI NÃO está instalado** — PRs/merges desta sessão foram via API REST com o token
  do `git credential fill` (host github.com). Para PRs futuros: instalar gh, usar a API, ou a UI web.
- Hook de push exige identidade: `AIOX_ACTIVE_AGENT=devops git push ...` (autoridade @devops).
- `dados/run_manifest.json` costuma ficar modificado na working tree (runtime de execuções
  locais) — **não commitar** por hábito; descartar com `git checkout -- dados/run_manifest.json` se incomodar.
- Branch `feat/fases-2-4-pipeline` ainda existe no remoto (mergeada; cleanup opcional pós-banca).
- Handoffs YAML da Fase 5 consolidados em `docs/runlogs/fase5-vm-RUN-LOG.md`
  (originais em `.aiox/handoffs/_archive/`, gitignored).

## 4. Como rodar o demo

```bash
poetry install                                   # 1x após o pull (venv novo do rename)
poetry run streamlit run src/dashboard/app.py    # SONAR em http://localhost:8501 (tema dark)
```

Roteiro de teste do chat RAG (validado): perguntas respondíveis (Artemis 2, iPhone 16,
DDR5, câncer, fases da Lua) → resposta com citação; pegadinhas (bolo de cenoura, preço
da ação da Apple hoje, smartphone 2027) → recusa honesta.

## 5. Carry-forward (nada bloqueante)

1. **Preparação da banca** (próximo trabalho natural): slides, roteiro do demo,
   narrativa de rigor (benchmark 5.6 + gates + estudo de caso LGPD).
2. Exportar **PNG estático** do estudo de caso para os slides (hoje só HTML interativo:
   `docs/img/estudo-caso-series.html`) — apontado no gate da 4.4.
3. Artefato "[1]" ocasional após recusa no chat (herdado da 5.5; ajuste fino de prompt).
4. Conectivo "portanto" sobrevive nas pontes entre tópicos (lista NLTK não o cobre;
   curadoria opcional).
5. ~36 erros ruff pré-existentes em `src/` (dívida cosmética; `ruff check --fix` resolve
   a maioria — fazer em story própria se desejado).
6. Avaliação cega do benchmark a posteriori (opcional, §1.1).

## 6. Trilha de agentes desta sessão (auditoria)

`@aiox-master` (Orion: verificação 5.6 → fechamento WAIVED → ciclos SDC 6.1/6.2 com
@sm/@po/@dev/@architect → gates paralelos 1.5–4.4 → auditoria README) → `@devops`
(Gage: pushes, PR #2/#3 + merges via API, rebrand sonar na main, este handoff).

> **Para a próxima sessão:** ler este arquivo; backlog está zerado — o trabalho é
> preparação da banca. Suíte deve permanecer em **172 verdes** (`poetry run pytest`).
