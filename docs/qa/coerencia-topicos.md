# Gate de Coerência SM2 — Clustering de Tópicos (Story 2.3 / AC3)

**Data:** 2026-07-06 · **Executor:** Dex (@dev) · **Veredito: ✅ PASS (93% ≥ 70%)**

## Corpus e parâmetros

| Item | Valor |
|---|---|
| Corpus | `dados/raw/corpus.parquet` — 6.423 artigos Olhar Digital, jan–jul/2026 (janela 4 meses do sitemap) |
| Embeddings | `paraphrase-multilingual-mpnet-base-v2` (768d, MPS) |
| Tópicos encontrados | **149** (+ 1.115 outliers em `-1`, 17,4% — esperado para HDBSCAN) |
| Parâmetros (config.yaml `clustering`) | `min_topic_size=10`, `min_cluster_size=10`, `n_neighbors=15`, `n_components=5`, `cluster_selection_epsilon=0.1`, `random_state=42`, `label_top_n=3` |

**Justificativa dos parâmetros:** `min_topic_size/min_cluster_size=10` filtram micro-clusters
de ruído num corpus de ~6,4 mil docs (os valores 2/2 usados na fase de amostra geravam
clusters instáveis); `random_state=42` garante reprodutibilidade; `language="multilingual"`
no BERTopic é obrigatório para PT-BR (o default "english" removia caracteres não-ASCII dos
termos — bug corrigido nesta execução).

## Metodologia

Amostra estratificada de **30 tópicos** (20% do total): os 15 maiores + 15 sorteados do
restante (`random_state=42`). Para cada tópico: top-5 termos c-TF-IDF + 4 títulos de
artigos-membro sorteados (`random_state=1`). Critério: o tópico é **coerente** quando os
títulos compartilham um assunto reconhecível e o label o descreve.

## Resultado por tópico

| Tópico | Label | Docs | Veredito |
|---|---|---|---|
| T0 | artemis missão nasa | 318 | ✅ |
| T1 | veículos carro de | 210 | ✅ |
| T2 | futebol copa horário | 192 | ✅ |
| T3 | netflix filme série | 157 | ✅ |
| T4 | spacex musk us | 112 | ✅ |
| T5 | portanto além disso disso | 93 | ❌ conectivos (filosofia/curiosidades misturadas) |
| T6 | células pacientes câncer | 92 | ✅ |
| T7 | lotofácil da lotofácil 05 | 84 | ✅ |
| T8 | watch smartwatch galaxy | 81 | ✅ |
| T9 | openai chatgpt da openai | 77 | ✅ |
| T10 | google gemini ia | 71 | ✅ |
| T11 | notebook intel gb | 69 | ✅ |
| T12 | cidade portanto além disso | 68 | ❌ conectivos (curiosidades geográficas/economia) |
| T13 | estrelas universo galáxias | 67 | ✅ |
| T14 | robôs robô humanoides | 66 | ✅ |
| T27 | fone bluetooth tws | 51 | ✅ |
| T37 | tv lg 4k | 42 | ✅ |
| T42 | uma casa obra quanto custa | 37 | ✅ |
| T56 | qled neo qled vision ai | 31 | ✅ |
| T57 | headset gamer | 30 | ✅ |
| T59 | cometa asteroide 3iatlas | 29 | ✅ |
| T68 | redmi xiaomi ram 256gb | 28 | ✅ |
| T75 | ia ataques sistemas | 24 | ✅ |
| T81 | arqueólogos do descoberta | 22 | ✅ |
| T88 | chocolate premiado mel | 20 | ✅ |
| T115 | chips tsmc de chips | 15 | ✅ |
| T116 | meteoros chuva | 15 | ✅ |
| T119 | fechadura senha chaves | 15 | ✅ |
| T126 | 99food ifood keeta | 14 | ✅ |
| T142 | plutão planeta isaacman | 11 | ✅ (com ressalva: mistura astrobiologia/Plutão, tema comum reconhecível) |

**Coerência: 28/30 = 93,3%** → **PASS** (limiar: ≥ 70%).

## Achados e melhorias futuras

1. **Tópicos de conectivos (T5, T12):** a lista de stopwords PT do NLTK não cobre
   conectivos discursivos ("portanto", "além disso"). Melhoria futura: estender a
   lista com conectivos. Impacto baixo — 2/149 tópicos (~2,5% dos docs).
2. **Contaminação pontual:** artigos "Olhar Digital News na íntegra" (resumo diário)
   aparecem em tópicos variados; candidato a filtro por título na limpeza.
3. **Outliers (17,4%):** dentro do esperado para HDBSCAN sem forçar atribuição;
   ficam fora do ranking (o dashboard filtra `topic_id = -1`).
