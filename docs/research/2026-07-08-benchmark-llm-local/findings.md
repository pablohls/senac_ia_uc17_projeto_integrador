# Benchmark de LLM local para a Camada de IA Generativa (PT-BR, 16GB VRAM)

**Data:** 2026-07-08
**Autor:** @analyst (Atlas)
**Contexto:** pendência do `docs/architecture/adr-002-camada-llm.md` — fixar `insight.model` para as tarefas *grounded* (rotulação de tópicos, briefing "por que sobe", RAG com citação), servidas via Ollama numa VM com **GPU de 16GB VRAM**.
**Método:** pesquisa web (jul/2026), priorizando dados atuais sobre memória (corte jan/2026). Fontes ao final.

---

## 1. Objetivo

Selecionar o(s) modelo(s) local(is) com melhor custo/benefício para **português do Brasil** em tarefas *grounded*, respeitando o teto de **16GB VRAM**. O owner apontou (corretamente) que há gerações mais novas que as da memória — a pesquisa confirmou e recalibrou os candidatos.

## 2. Panorama de modelos (julho/2026) que cabem em 16GB

Famílias confirmadas como **existentes e atuais**:

| Família | Lançamento | Sizes relevantes p/ 16GB | Notas |
|---|---|---|---|
| **Qwen2.5** | 2024 | 7B, 14B | "Melhor modelo local para línguas não-inglesas"; PT-BR near-native |
| **Qwen3** | 2025 | 8B, 14B, 30B-A3B (MoE) | Dual-mode (thinking/non-thinking); 119 línguas |
| **Qwen3.5** | 16/02/2026 | **9B** (denso), 2B, 27B | **201 línguas, 256K contexto**, multimodal; "best quality-per-GB" em 16GB |
| **Qwen3.6** | abr/2026 | 35B-A3B (MoE), 27B denso | Contexto nativo de 1M; 27B denso não cabe em 16GB |
| **Gemma 3** | 12/03/2025 | 4B, **12B**, 27B | **140 línguas, 128K contexto**, multimodal |
| **Gemma 4** | abr/2026 | E2B, E4B, **9B?**, 26B MoE, 31B denso | Tool calling + JSON estruturado forte; 31B denso não cabe |
| **GPT-OSS** | 2025 | 20B (MoE) | Rápido (140 tok/s), cabe em 16GB, **multilíngue fraco** |

> **Ajuste de VRAM (4-bit):** 9B ≈ 6–7GB · 12–14B ≈ 9–10GB · 26–31B denso ≈ 18–20GB (**não cabe**). MoE ocupa a VRAM do total de parâmetros (só a *computação* usa os ativos), então 26B-MoE fica no limite dos 16GB.

## 3. Achado-chave (o que muda a decisão) 🔎

**Em PT-BR, "o mais novo" NÃO é automaticamente o melhor.** No **Open PT-LLM Leaderboard** (ENEM, BLUEX, OAB, ASSIN2 etc.):

- **Qwen2.5 → 52,25** de média geral
- **Qwen3 → 46,47** (ou seja, *abaixo* do Qwen2.5)
- **Gemma 3 → 40,40** (mas forte em tarefas específicas, ex.: classificação de ofensa HateBR)

Ou seja: uma geração mais nova (Qwen3) **regrediu** no benchmark de português frente à anterior (Qwen2.5). Isso é comum — ganhos gerais (código, raciocínio) às vezes vêm com perda de cobertura em línguas específicas.

**Lacuna de evidência (honestidade metodológica):** os modelos **mais novos** (Qwen3.5 9B, Gemma 4) **ainda não aparecem** nos leaderboards públicos de PT-BR que encontrei. Sua qualidade em português para o *nosso* uso é, hoje, **não verificada por benchmark independente**.

**Modelos PT-nativos (Tucano 2, Amadeus-Verbo, Curió):** existem e superam multilíngues *de mesmo tamanho* em PT, mas nas faixas pequenas (0,5B–7B). Para geração de **narrativa fluida** (briefing), o tamanho pesa — provavelmente abaixo do que queremos. Vale como curiosidade/menção, não como primária.

## 4. Implicação para tarefas *grounded* (nosso caso)

Nossas tarefas são **fundamentadas** (o modelo recebe os artigos): rotular tópico, explicar "por que sobe", responder RAG citando fonte. Isso:
- **reduz a exigência** de conhecimento de mundo do modelo (o contexto entrega os fatos);
- **valoriza contexto longo** (RAG) → Qwen3.5 9B (256K) e Gemma 3 12B (128K) levam vantagem;
- **valoriza saída estruturada** (rótulos/JSON) → Gemma 4 e Qwen3 têm bom tool/JSON.

Conclusão: nesta classe de tarefa, a diferença entre um 9B e um 14B bons **tende a ser pequena** — o desempate real é **fluência em PT-BR** e **latência**, que só se medem no nosso corpus.

## 5. Shortlist recomendada (3 finalistas)

| # | Modelo | Ollama | VRAM (4-bit) | Por que está na lista |
|---|---|---|---|---|
| 1 | **Qwen2.5-14B-Instruct** | `qwen2.5:14b` | ~9–10GB | **Líder comprovado em PT-BR** (52,25); default atual do ADR — a pesquisa o *valida* |
| 2 | **Qwen3.5-9B** | `qwen3.5:9b` | ~6–7GB | Mais novo, 256K contexto (ótimo p/ RAG), "best quality-per-GB", muita folga de VRAM |
| 3 | **Gemma 3-12B-it** | `gemma3:12b` | ~9–10GB | 140 línguas, 128K contexto, saída estruturada; PT-BR sólido e verificado em tarefas |

**Descartados e por quê:**
- *Gemma 4 31B / Qwen3.6 27B denso* — não cabem em 16GB.
- *GPT-OSS 20B* — cabe e é rápido, mas multilíngue fraco (contra o requisito PT-BR).
- *Tucano 2 / PT-nativos pequenos* — bons em PT no seu tamanho, mas pequenos demais para narrativa fluida.
- *Qwen3-14B "puro"* — regrediu em PT-BR vs Qwen2.5; sem motivo para preferir ao 2.5 na nossa tarefa.

## 6. Recomendação

**Não fixar por leaderboard — decidir por teste empírico no nosso corpus, com a shortlist acima.** Justificativa:
1. os leaderboards de PT-BR não cobrem os modelos mais novos nas nossas faixas;
2. a tarefa é *grounded*, então benchmark geral prediz mal o resultado prático;
3. o teste é barato: mesmos prompts, ~10 tópicos reais, 3 modelos via Ollama, comparar rótulo/"por que sobe"/latência.

**Se for preciso escolher UM sem teste** (ex.: prazo): **Qwen2.5-14B** — é o único com evidência *direta* de liderança em PT-BR, e já é o default do ADR. Mantém a decisão defensável na banca ("escolhido por benchmark público de português, não por hype").

**Ganho de banca:** poder dizer *"testamos 3 gerações (2.5, 3.5, Gemma 3), medimos em PT-BR no nosso próprio corpus, e a escolha é justificada por dado — não pelo mais recente"* é exatamente o tipo de rigor que impressiona.

## 7. Próximo passo sugerido

Rodar o **protocolo empírico** (a opção híbrida): esta pesquisa entregou a shortlist; um teste A/B/C nos tópicos reais crava o vencedor e vira evidência para o relatório final. Alternativamente, aceitar Qwen2.5-14B como default e seguir para as stories (@sm).

---

## Fontes

- [Gemma (language model) — Wikipedia](https://en.wikipedia.org/wiki/Gemma_(language_model))
- [Gemma 4 model overview — Google AI for Developers](https://ai.google.dev/gemma/docs/core)
- [Welcome Gemma 3 — Hugging Face](https://huggingface.co/blog/gemma3)
- [Qwen 3 Full Lineup Guide 2026 — RockB](https://baeseokjae.github.io/posts/qwen-3-full-lineup-guide-2026/)
- [Qwen 3 & 3.5 GPU Requirements (2026) — Will It Run AI](https://willitrunai.com/blog/qwen-3-gpu-requirements)
- [Best Open Source LLM Models for 16GB VRAM in 2026 — Pactentia](https://pactentia.com/blog/best-open-source-llm-16gb-vram-2026)
- [Best Local LLMs for 16GB VRAM — LocalLLM.in](https://localllm.in/blog/best-local-llms-16gb-vram)
- [Tucano 2: Better Open Source LLMs for Portuguese — arXiv 2603.03543](https://arxiv.org/html/2603.03543v1)
- [CLARIN-PT-LDB: Open LLM Leaderboard for Portuguese — arXiv 2603.12872](https://arxiv.org/pdf/2603.12872)
- [Best Open-Source LLMs: July 2026 Leaderboard — TECHSY](https://techsy.io/en/blog/best-open-source-llms-2026)

> **Limitações:** notas de leaderboard vêm de sínteses de fontes secundárias, não de re-execução independente dos benchmarks; modelos mais recentes (Qwen3.5, Gemma 4) carecem de avaliação pública em PT-BR nas faixas-alvo. Daí a recomendação de teste empírico local.
