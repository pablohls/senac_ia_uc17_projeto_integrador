# Resultado do benchmark A/B/C — LLM local (Story 5.6)

**Modelos medidos:** gemma3:12b, qwen2.5:14b, qwen3.5:9b
**Protocolo:** `protocolo-empirico.md` | **Amostra:** `amostra_benchmark.json` (congelada) | **Brutos:** `resultados_brutos.parquet`

## Desempenho (medição automática)

| modelo | tarefa | latencia_1o_token_s | latencia_total_s | tokens_por_s | vram_pico_mb | n |
|---|---|---|---|---|---|---|
| gemma3:12b | T1 | 2.17 | 2.3 | 5.87 | 10958.0 | 12 |
| gemma3:12b | T2 | 1.06 | 2.84 | 41.44 | 10958.0 | 12 |
| gemma3:12b | T3 | 1.28 | 2.51 | 28.88 | 10958.0 | 8 |
| qwen2.5:14b | T1 | 1.89 | 2.01 | 9.73 | 11237.0 | 12 |
| qwen2.5:14b | T2 | 0.55 | 2.54 | 51.6 | 11237.0 | 12 |
| qwen2.5:14b | T3 | 0.62 | 1.65 | 35.75 | 11237.0 | 8 |
| qwen3.5:9b | T1 | 19.41 | 19.49 | 0.45 | 8597.0 | 6 |
| qwen3.5:9b | T2 | 17.94 | 19.03 | 5.56 | 8597.0 | 9 |
| qwen3.5:9b | T3 | 19.47 | 20.15 | 2.54 | 8597.0 | 6 |

> Tokens aproximados pelo nº de fragmentos do stream (~1 token/chunk no Ollama). VRAM = `memory.used` global da GPU (inclui o encoder do retriever, ~igual para todos os modelos — comparação justa). Budget uniforme de 4096 tokens por chamada (> produção, 512): modelos *thinking* gastam >1.500 tokens de raciocínio antes do 1º token de conteúdo e NÃO produzem saída sob o contrato de produção — a latência do 1º token aqui é até o 1º token de CONTEÚDO (raciocínio conta no tempo, não nos tokens).

## Confiabilidade (chamadas sem saída sob o budget do harness)

| modelo | chamadas | sem_saida | taxa_falha |
|---|---|---|---|
| gemma3:12b | 32 | 0 | 0.0 |
| qwen2.5:14b | 32 | 0 | 0.0 |
| qwen3.5:9b | 32 | 11 | 0.34 |

> Falha = a chamada terminou sem NENHUM token de conteúdo (ex.: modelo *thinking* estourou o budget só raciocinando). Itens com falha ficam fora da avaliação cega daquele modelo.

## Qualidade (avaliação cega) — NÃO EXECUTADA (dispensada por decisão da equipe)

A pontuação humana foi formalmente dispensada em 2026-07-09. Justificativa:

- **`qwen3.5:9b` foi eliminado por confiabilidade**, não por qualidade: 0% de saída sob o contrato de produção (512 tokens), 34% de falha mesmo com 8× o budget, ~17s até o 1º token útil. Nenhuma nota de qualidade reverteria a eliminação.
- Entre os dois finalistas (ambos 100% confiáveis), `qwen2.5:14b` vence todas as métricas medidas — latência de 1º token (0,56s vs 1,08s) e throughput (38 vs 32 tok/s), com VRAM equivalente — e **ambos recusaram honestamente as 3 pegadinhas RAG** (sinal parcial do critério eliminatório de fidelidade, protocolo §7).
- O vencedor em desempenho/confiabilidade coincide com o default já firmado no ADR-002. A avaliação cega só seria necessária para justificar uma **troca** de modelo — não há indício que a motive.

A planilha `avaliacao_cega.csv` e o `mapa_cego.json` permanecem no repositório: a avaliação pode ser executada a posteriori, sem repetir as medições, via `poetry run python scripts/benchmark_llm.py consolidar --avaliacoes <arquivos.csv>`.

## Recomendação final

**Manter `qwen2.5:14b` como `insight.model`.** Sem alteração de configuração e sem mudança no ADR-002 (a decisão original fica validada pela medição empírica).

## Limitações declaradas

- Amostra pequena (20 itens): sinal **qualitativo**, não significância estatística (protocolo §9).
- Mesma quantização (Q4 default do Ollama) e mesmos prompts de produção para todos — nenhum prompt foi tunado por modelo.
- **Qualidade textual entre `qwen2.5:14b` e `gemma3:12b` não foi pontuada por humanos** — a decisão apoia-se em confiabilidade, desempenho medido e no sinal parcial de fidelidade (recusa das pegadinhas RAG).
