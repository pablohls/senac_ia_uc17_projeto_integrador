# Protocolo Empírico — Escolha do LLM local (A/B/C no corpus real)

**Data:** 2026-07-08
**Autor:** @analyst (Atlas)
**Status:** opcional / não-bloqueante (o ADR-002 já firmou `qwen2.5:14b` como default por pesquisa)
**Objetivo:** validar — ou refutar — a escolha do modelo **no nosso próprio corpus e tarefas**, produzindo evidência defensável para a banca.

---

## 1. Hipótese

> H0: para as tarefas *grounded* do SONAR (rotulação, "por que sobe", RAG), a diferença de qualidade em PT-BR entre os 3 finalistas é pequena, e **Qwen2.5-14B** é ≥ que os demais.
>
> H1: algum modelo mais novo (Qwen3.5-9B / Gemma 3-12B) supera o Qwen2.5-14B em qualidade PT-BR **ou** empata em qualidade com latência/VRAM materialmente melhores.

Decisão prática: se H0 se sustenta → mantém o default. Se H1 → troca `insight.model` (1 linha no YAML).

## 2. Modelos sob teste

| ID | Modelo | Comando |
|----|--------|---------|
| **A** | Qwen2.5-14B-Instruct | `ollama pull qwen2.5:14b` |
| **B** | Qwen3.5-9B | `ollama pull qwen3.5:9b` |
| **C** | Gemma 3-12B-it | `ollama pull gemma3:12b` |

Mesma quantização (Q4 default do Ollama), mesmo endpoint OpenAI-compatible, `temperature=0` (batch) — isola a variável "modelo".

## 3. Amostra (fixa para os 3 modelos)

**~12 tópicos reais**, estratificados a partir dos artefatos existentes (`scores.parquet`, `topic_info.parquet`), para cobrir casos fáceis e difíceis:

- **6 tópicos do topo do ranking** (`trend_score` alto, `support_ok=True`) — o caso principal.
- **1 tópico com alerta da Camada 2** (o T35 "iphone apple", z=2,66) — caso de anomalia.
- **2 tópicos ruidosos conhecidos** (T5, T12 — conectivos; handoff) — testa robustez do rótulo.
- **2 tópicos de nicho / baixo suporte** — testa se o modelo "inventa" quando há pouca evidência.
- **1 tópico multi-tema** (ex.: "Olhar Digital News na íntegra") — testa foco.

**Para o RAG:** 8 perguntas fixas em PT-BR (5 respondíveis pelo corpus, 3 "pegadinhas" sem resposta no corpus — testa se o modelo admite "não sei" em vez de alucinar).

> A amostra é **congelada** num arquivo (`amostra_benchmark.json`) antes de rodar — mesmos itens, mesma ordem interna, para os 3 modelos.

## 4. Tarefas medidas (idênticas às da feature)

| Tarefa | Entrada | Saída avaliada |
|--------|---------|----------------|
| **T1 — Rótulo** | top-5 títulos do tópico | nome semântico curto (≤ 8 palavras) |
| **T2 — "Por que sobe"** | top-5 artigos (título+trecho) + métrica de crescimento | parágrafo (2-4 frases) |
| **T3 — RAG** | pergunta + top-k trechos recuperados | resposta + citações (URLs) |

Prompts **fixos** (os mesmos que irão para produção — `src/insight/prompts.py`), variando só o modelo.

## 5. Métricas

### 5.1 Qualidade (avaliação cega, humana) — rubrica 1–5

| Critério | Aplica a | O que mede |
|----------|----------|------------|
| **Fluência PT-BR** | T1, T2, T3 | gramática, naturalidade, acentuação correta |
| **Fidelidade (groundedness)** | T2, T3 | afirma **só** o que os artigos sustentam (0 alucinação) |
| **Relevância / foco** | T1, T2 | captura o tema real, sem generalidade vazia |
| **Citação correta** | T3 | as URLs citadas existem e sustentam a resposta |
| **Recusa honesta** | T3 (pegadinhas) | admite ausência de resposta em vez de inventar |

Escala: 1 (ruim) … 5 (excelente). **Avaliação cega:** as saídas dos 3 modelos são embaralhadas e anonimizadas (rótulo A/B/C oculto) antes de pontuar.

### 5.2 Desempenho (medido automaticamente)

- **Latência:** tempo até 1º token + tempo total por tarefa (média sobre a amostra).
- **Throughput:** tokens/segundo.
- **VRAM de pico:** `nvidia-smi` durante a inferência.

## 6. Procedimento

1. **Preparar** — `ollama pull` dos 3 modelos; congelar `amostra_benchmark.json`.
2. **Executar** — harness (`scripts/benchmark_llm.py`) percorre {3 modelos × 12 tópicos × 3 tarefas + 8 perguntas RAG}, grava saídas + latência/VRAM em `resultados_brutos.parquet`. Reaproveita `src/common/llm.py` (só troca `base_url`/`model`).
3. **Anonimizar** — gerar planilha cega (saídas embaralhadas, sem revelar o modelo).
4. **Avaliar** — **≥ 2 avaliadores humanos** (integrantes da equipe) pontuam de forma independente; medir concordância (ex.: correlação simples). Divergência > 1 ponto → 3º avaliador desempata.
5. **Consolidar** — média por critério/modelo + tabela de latência/VRAM.

## 7. Regra de decisão

1. **Qualidade primeiro:** vence quem tiver **maior média ponderada de qualidade** (peso maior em *Fidelidade* e *Fluência PT-BR* — são o núcleo do produto).
2. **Empate técnico** (diferença de qualidade ≤ 0,3 na média): vence o de **menor latência / menor VRAM** (mais folga na VM, resposta mais rápida no demo ao vivo).
3. **Fidelidade é eliminatória:** qualquer modelo com alucinação frequente no RAG (nota média de Fidelidade < 3) é descartado, mesmo com boa fluência.

Resultado → atualizar `insight.model` no `config.yaml` e registrar a decisão no ADR-002 (Change Log).

## 8. Entregáveis

- `scripts/benchmark_llm.py` — harness reproduzível (@dev).
- `amostra_benchmark.json` — amostra congelada.
- `resultados_brutos.parquet` + planilha de avaliação cega.
- `resultado-benchmark.md` — tabela final + recomendação (atualiza este diretório).

## 9. Ameaças à validade (e mitigação)

| Ameaça | Mitigação |
|--------|-----------|
| Viés do avaliador (sabe qual é o "favorito") | avaliação **cega** (A/B/C embaralhados) |
| Amostra pequena (12 tópicos) | estratificação por dificuldade; suficiente para sinal qualitativo, não p/ significância estatística — declarar isso |
| Quantização Q4 pode penalizar modelos diferentemente | padronizar Q4; registrar; se dúvida, repetir com Q5 no vencedor |
| Prompt favorece um estilo de modelo | usar o **mesmo** prompt de produção para todos; não tunar por modelo |

## 10. Esforço estimado

- Setup + harness: ~meio dia (@dev).
- Execução (3 modelos): ~1–2h de GPU (batch).
- Avaliação cega (2 pessoas): ~1–2h.

> **Custo/benefício:** baixo esforço, e transforma "escolhemos o Qwen2.5" em "**medimos 3 gerações em PT-BR no nosso corpus, com avaliação cega, e a escolha é justificada por dado**" — narrativa forte para a banca.
