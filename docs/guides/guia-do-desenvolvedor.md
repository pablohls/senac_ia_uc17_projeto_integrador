# SONAR — Guia do Desenvolvedor

**Guia de estudo: como tudo foi feito e por quê, explicado do zero.**
Público: os desenvolvedores do projeto, preparando-se para a banca.
Data: 2026-07-10 · Documento-irmão: [Relatório do Projeto](../relatorio-projeto.md)

> **Como usar este guia:** se você travar em alguma sigla (c-TF-IDF, LSTM, RAG, embedding...), pule para o **[Dicionário de termos](#dicionário-de-termos)** na seção 2 — ele explica cada conceito em uma ou duas frases, com analogia. Cada seção técnica também tem um bloco **"Em palavras simples"** antes da parte detalhada. Leia o simples primeiro; o detalhe fica para quando precisar do número exato.

---

## Sumário

1. [Visão geral: o que o SONAR faz](#1-visão-geral-o-que-o-sonar-faz)
2. [Dicionário de termos](#dicionário-de-termos)
3. [Como rodar](#3-como-rodar)
4. [Arquitetura: por que o projeto é uma "linha de montagem"](#4-arquitetura-por-que-o-projeto-é-uma-linha-de-montagem)
5. [Fase 1 — Coleta (buscar as notícias)](#5-fase-1--coleta-buscar-as-notícias)
6. [Fase 2 — PLN e tópicos (descobrir os assuntos)](#6-fase-2--pln-e-tópicos-descobrir-os-assuntos)
7. [Fase 3 — Scores (medir o que está bombando)](#7-fase-3--scores-medir-o-que-está-bombando)
8. [Fase 5 — IA generativa (explicar e conversar)](#8-fase-5--ia-generativa-explicar-e-conversar)
9. [Fases 4 e 6 — Dashboard](#9-fases-4-e-6--dashboard)
10. [Metodologia e histórico](#10-metodologia-e-histórico)
11. [Q&A de banca](#11-qa-de-banca)
12. [Limitações e mitigações](#12-limitações-e-mitigações)

---

## 1. Visão geral: o que o SONAR faz

O SONAR lê milhares de notícias de tecnologia em português, descobre **sozinho** quais são os assuntos, mede **quais estão crescendo** e **explica em português** por que estão crescendo. Pense nele como um assistente que lê todos os portais de tecnologia por você e avisa: *"olha, o assunto X disparou essa semana — e é por isso."*

**O problema que resolve:** saem centenas de notícias de tech por dia. Ninguém consegue ler tudo, e quem tenta perceber tendências no olho descobre tarde e sem prova. O Google Trends mede o que as pessoas *pesquisam* (não o que os jornalistas *escrevem*), não separa os assuntos automaticamente e só mostra uma curva — sem dizer o porquê.

**O que o SONAR faz, em 4 verbos:**

| Verbo | O que significa | Como |
|---|---|---|
| **Descobre** | acha os assuntos sem lista pronta | agrupa notícias parecidas automaticamente (BERTopic) |
| **Nomeia** | dá um nome a cada assunto | pega as palavras que mais caracterizam o grupo |
| **Mede** | diz o quanto cada assunto acelera | uma nota de tendência (Trend Score) |
| **Explica** | conta o porquê, em português | uma IA que escreve um resumo e conversa com você |

**A "linha de montagem" do SONAR** (cada caixa entrega um arquivo para a próxima):

```
CONFIG (todos os parâmetros num só lugar)
   │
[Fase 1] COLETA  →  baixa as notícias e monta uma tabela de artigos
   │
[Fase 2] PLN     →  limpa o texto, transforma em números e agrupa em assuntos
   │
[Fase 3] SCORES  →  conta artigos por dia e calcula a nota de tendência
   │
[Fase 5] IA      →  escreve o "porquê" de cada assunto em alta
   │
[Fase 4/6] DASHBOARD  →  a tela que mostra tudo + chat que responde perguntas
```

Tudo isso foi feito sob restrições reais: ~2 semanas de prazo para o MVP, 4 pessoas, 1 computador com GPU, zero orçamento, e a exigência de que a demonstração para a banca funcione sempre igual, sem depender de internet.

---

## Dicionário de termos

Consulte quando travar. Agrupado por área; cada termo em linguagem simples.

### Conceitos gerais

- **Pipeline / linha de montagem** — a sequência de etapas do projeto, cada uma pegando o resultado da anterior. Coleta → PLN → Scores → IA → Dashboard.
- **Corpus** — o conjunto de todos os textos que o sistema analisa (aqui, os artigos coletados).
- **Artefato / contrato** — o arquivo que uma etapa entrega para a próxima. "Contrato" porque o formato (as colunas) é combinado e fixo, como um contrato entre as etapas.
- **Parquet** — um formato de tabela (como uma planilha de Excel ou um CSV), mas comprimido e rápido de ler. É o formato dos arquivos que as etapas trocam entre si.
- **Schema** — a "estrutura" de uma tabela: quais colunas ela tem e de que tipo (texto, data, número).
- **Hash / SHA-1** — a "impressão digital" de um texto: o mesmo texto sempre gera o mesmo código curto, e é praticamente impossível dois textos diferentes gerarem o mesmo. Usamos a impressão digital da URL como identidade única de cada artigo (`doc_id`).
- **Config / parâmetro** — um valor ajustável do sistema (ex.: "coletar 4 meses", "alertar a partir de 2,5"). No SONAR, todos ficam num único arquivo (`config/config.yaml`).
- **Determinístico / reprodutível** — rodar de novo dá exatamente o mesmo resultado. Importante para a banca poder repetir a demonstração.
- **Degradação graciosa** — quando uma parte opcional falha, o sistema continua funcionando sem ela em vez de quebrar tudo. Como um carro que perde o ar-condicionado mas continua andando.

### Coleta (Fase 1)

- **Sitemap** — um "índice do site" que cada portal publica (um arquivo XML) listando os endereços de todas as suas páginas. É feito justamente para robôs de busca lerem.
- **RSS** — um feed de notícias recentes. Descartamos porque só mostra ~12 itens do dia — não dá para pegar meses de histórico.
- **API** — uma porta de entrada oficial para pegar dados de um sistema de forma programada. Os portais não oferecem uma.
- **Parsing** — "ler de forma estruturada": pegar um arquivo (HTML, XML) e extrair dele as informações que interessam.
- **trafilatura** — a biblioteca que, dada a página de uma notícia, devolve só o texto do artigo (sem menu, propaganda, comentários).
- **Rate-limit** — limite de velocidade: esperar ~1 segundo entre um download e outro para não sobrecarregar o portal.
- **robots.txt** — arquivo em que o site diz o que robôs podem ou não acessar. Nós respeitamos.
- **User-Agent** — a "identidade" que o programa apresenta ao site ("sou o SONAR, projeto acadêmico").
- **Deduplicação (dedup)** — remover artigos repetidos (mesma URL).
- **Incremental** — em vez de baixar tudo de novo toda vez, baixar só o que é novo.

### PLN e tópicos (Fase 2)

- **PLN (Processamento de Linguagem Natural)** — a área da computação que faz o computador "entender" texto humano.
- **Embedding** — a tradução de um texto para uma **lista de números** que representa o seu *significado*. Textos com sentido parecido viram listas de números parecidas. Analogia: é como dar a cada artigo um endereço numa "cidade de significados" — artigos sobre o mesmo assunto ficam em bairros vizinhos. No SONAR cada artigo vira uma lista de **768 números**.
- **Vetor / dimensões (768d)** — a tal lista de números. "768 dimensões" quer dizer "lista de 768 números". Não dá para desenhar, mas o computador calcula distâncias entre elas normalmente.
- **Similaridade de cosseno** — a conta que mede se dois embeddings (duas listas de números) "apontam para a mesma direção", ou seja, se dois textos têm significado parecido. Perto de 1 = muito parecido.
- **Sentence-Transformers** — a biblioteca que gera os embeddings. Usamos um modelo **multilíngue** (funciona em português).
- **Clustering / agrupamento** — juntar automaticamente as coisas parecidas em grupos.
- **Tópico** — cada grupo de artigos sobre o mesmo assunto que o sistema descobre.
- **BERTopic** — a ferramenta que descobre os tópicos. Ela junta três peças: UMAP + HDBSCAN + c-TF-IDF (abaixo).
- **UMAP** — encolhe cada embedding de 768 números para só 5, mantendo quem está perto de quem. Por quê? O algoritmo de agrupamento "se perde" quando há números demais (ver *maldição da dimensionalidade*). Analogia: achatar um globo terrestre num mapa de papel preservando os países vizinhos.
- **HDBSCAN** — o algoritmo que forma os grupos por **densidade**: onde há muitos artigos amontoados, cria um tópico; artigos isolados ficam "sem tópico". Vantagem: não precisa dizer de antemão quantos tópicos existem, e separa o "lixo".
- **Outlier** — um artigo que não se encaixa em nenhum grupo (fica no tópico especial `-1`). No SONAR, 21,3% dos artigos são outliers — e isso é proposital (ver §6.3).
- **c-TF-IDF** — o método que **descobre o nome de cada tópico**. Ele acha as palavras que são *características* daquele grupo: frequentes dentro dele e raras nos outros. Ex.: se um grupo fala muito "iphone", "apple", "ios" e os outros grupos quase não usam essas palavras, elas viram o nome do tópico. (O nome vem de "TF-IDF baseado em classe": TF-IDF é a técnica clássica de achar as palavras marcantes de *um documento*; o "c-" faz o mesmo para um *grupo inteiro* de documentos, tratando o grupo como se fosse um documentão.)
- **Stopwords** — palavras que aparecem em tudo e não dizem nada sobre o assunto ("de", "a", "que", "para"). São filtradas para não virarem nome de tópico.
- **LDA** — um método mais antigo de achar tópicos, baseado só em contar palavras (não entende significado). Foi descartado em favor do BERTopic.
- **K-means** — outro método de agrupamento, que exige dizer quantos grupos existem e força todo artigo para algum grupo. Descartado (o HDBSCAN é melhor para texto ruidoso).
- **Maldição da dimensionalidade** — o fenômeno de que, com números demais (768), a noção de "perto/longe" perde sentido e os algoritmos de agrupamento falham. Por isso o UMAP encolhe para 5 primeiro.
- **Coerência de tópicos** — uma medida de qualidade: os artigos de um tópico realmente falam da mesma coisa? Avaliamos à mão e deu 93%.

### Scores de tendência (Fase 3)

- **Série temporal** — uma sequência de valores ao longo do tempo. Aqui: quantos artigos por dia cada tópico teve.
- **Zero-fill** — preencher com 0 os dias em que um tópico não teve nenhum artigo (senão as contas ficariam infladas, olhando só os dias "bons").
- **Trend Score** — a **nota de tendência** de cada tópico: o quanto ele está em alta. Quanto maior, mais o assunto está acelerando.
- **Média móvel** — a média dos últimos N dias, que "suaviza" os altos e baixos diários. Usamos janelas de 7 dias.
- **Logaritmo (log)** — uma função matemática que "comprime" números grandes. Serve para um assunto gigante não esmagar todos os outros só pelo tamanho.
- **Suavização de Laplace** — um truquezinho de somar 1 numa divisão para nunca dividir por zero (e não exagerar quando os números são minúsculos).
- **Média (μ) e desvio-padrão (σ)** — a média é o valor típico; o desvio-padrão é o "quanto costuma variar em torno da média". São a base do z-score.
- **z-score (z)** — mede **quão fora do normal** um valor está, contando em desvios-padrão. Ex.: se um tópico costuma ter 2 artigos/dia (variação típica de 1) e hoje teve 10, isso está a 8 desvios da média — muito anormal. z alto = anormal.
- **Burst / surto** — um pico repentino de artigos sobre um tópico.
- **Rede neural** — um modelo de IA inspirado no cérebro, que aprende padrões a partir de exemplos.
- **LSTM** — um tipo de rede neural com "memória", boa para aprender padrões em **sequências** (como uma série de dias). Ela olha o histórico de um tópico e prevê quantos artigos virão no próximo dia.
- **Previsão one-step-ahead** — prever só o próximo ponto (o dia seguinte), não o futuro distante.
- **surprise_z (score de surpresa)** — o mesmo tipo de conta do z-score, mas comparando o valor real com o que a **LSTM previu**. Se a LSTM esperava 5 artigos e vieram 15, isso é uma "surpresa" grande. Mede o tamanho da surpresa em desvios-padrão do erro típico. Acima de 2,5, vira **alerta de anomalia**.
- **Baseline de persistência** — a previsão mais simples possível: "amanhã vai ser igual a hoje". Serve de **régua**: se a LSTM (complexa) não consegue prever melhor que esse chute bobo, ela não vale a pena. É a nossa prova de honestidade.
- **Hold-out** — separar um pedaço final da série e **escondê-lo** do treino, para testar a previsão em dias que o modelo nunca viu. Como estudar com metade das questões e se testar com a outra metade.
- **MAE / RMSE** — duas formas de medir o **erro** de uma previsão (o quanto ela erra na média). Menor = melhor.
- **Overfitting** — quando o modelo "decora" os dados de treino em vez de aprender o padrão, e vai mal em dados novos. O hold-out serve para detectar isso.
- **Seed (semente)** — um número que fixa a parte aleatória do treino, para o resultado sair sempre igual (reprodutibilidade). Usamos 42.
- **Backtest** — testar o sistema "voltando no tempo": fingir que hoje é uma data passada, esconder tudo depois dela, e ver se o SONAR teria apontado a tendência certa.
- **Vazamento de futuro (data leakage)** — o erro de deixar o modelo "espiar" dados do futuro durante um teste, o que faz o resultado parecer bom sem ser. Tomamos cuidado explícito para evitar.
- **ARIMA / Prophet** — métodos clássicos (não-IA) de previsão de séries. Descartados porque o curso exigia Deep Learning.

### IA generativa (Fase 5)

- **LLM (Large Language Model)** — um "modelo de linguagem grande", tipo o ChatGPT: uma IA treinada para entender e gerar texto. Usamos um que roda no nosso próprio computador.
- **Ollama** — o programa que roda o LLM localmente, na nossa máquina (sem internet, sem nuvem).
- **qwen2.5:14b** — o LLM que escolhemos. "14b" = 14 bilhões de parâmetros (o "tamanho" do modelo).
- **Parâmetros (de um modelo)** — os "botões" internos que o modelo aprendeu; mais parâmetros ≈ modelo maior e mais capaz, mas mais pesado.
- **Quantização Q4** — comprimir os números internos do modelo (de 16 bits para 4) para ele **caber na memória da GPU**. Perde um tiquinho de precisão, ganha muito espaço.
- **VRAM** — a memória da placa de vídeo (GPU). A nossa tem 16 GB, o que limita o tamanho do modelo.
- **Token** — o pedacinho de texto que o LLM processa por vez (~¾ de uma palavra). "max_tokens=512" limita o tamanho da resposta.
- **Temperatura** — o controle de "criatividade" do LLM. 0 = sempre a resposta mais provável (previsível, reproduzível); mais alto = mais variação.
- **Prompt** — a instrução/texto que mandamos para o LLM.
- **RAG (Retrieval-Augmented Generation)** — a técnica do nosso chat: em vez de o LLM responder "de cabeça" (e arriscar inventar), primeiro **buscamos** os trechos mais relevantes dos nossos artigos e os entregamos junto com a pergunta; o LLM responde **lendo esses trechos** e citando a fonte. Analogia: uma prova com consulta em que você é obrigado a citar a página de onde tirou a resposta.
- **Grounding / grounded** — "ancorado": obrigar o LLM a responder apenas com base nos dados fornecidos, não no que ele "acha".
- **Alucinação** — quando o LLM inventa uma informação que soa convincente mas é falsa. O RAG e as citações servem para combater isso.
- **Cold start** — a primeira chamada ao modelo é lenta (~60s) porque ele precisa ser carregado na memória da GPU. As seguintes são rápidas.
- **Streaming** — a resposta aparecer palavra por palavra (como no ChatGPT), em vez de tudo de uma vez — dá sensação de rapidez.
- **OpenAI-compatible** — o nosso código fala com o LLM no mesmo "idioma" (formato de API) que a OpenAI usa. Vantagem: trocar o modelo local por um da nuvem é mudar uma linha de config.
- **Fine-tuning** — retreinar um modelo com dados próprios. Descartado (caro e desnecessário aqui).

### Dashboard

- **Streamlit** — a ferramenta que usamos para construir a tela (dashboard) em Python puro, sem precisar programar site.
- **Precompute-then-serve** — "calcular antes, mostrar depois": o dashboard só **lê** resultados já prontos; ele não faz conta pesada na hora, por isso abre rápido.
- **Grafo** — um desenho de bolinhas (nós) ligadas por linhas (arestas). Usamos para mostrar termos que aparecem juntos.
- **Co-ocorrência** — dois termos que aparecem no mesmo tópico com frequência (ficam ligados no grafo).

---

## 3. Como rodar

```bash
# Setup (uma vez): instala tudo num ambiente isolado
poetry install

# Rodar o pipeline usando o corpus congelado (SEM internet) — é o modo do demo
poetry run sonar

# Rodar incluindo a coleta de notícias (as duas fontes levam ~6h na 1ª vez; depois é incremental)
poetry run sonar --com-coleta

# Abrir o dashboard
poetry run streamlit run src/dashboard/app.py

# Ligar a IA generativa (opcional — sem ela, o dashboard funciona igual, só sem os textos da IA)
ollama serve && ollama pull qwen2.5:14b
poetry run python -m src.insight.run

# Rodar os testes
poetry run pytest         # 172 testes
```

Por que a coleta é opcional? Porque a demonstração precisa funcionar sempre igual e sem internet. Por isso o SONAR guarda um "corpus congelado" (um conjunto fixo de artigos já baixados) e o modo padrão parte dele.

---

## 4. Arquitetura: por que o projeto é uma "linha de montagem"

**Em palavras simples:** o SONAR é uma sequência de etapas em que cada uma pega um arquivo, faz seu trabalho e entrega outro arquivo para a próxima. Não há um "programa gigante" — são peças independentes ligadas por arquivos. Isso permitiu que **4 pessoas trabalhassem em paralelo**: cada um cuidava de uma etapa, e como o **formato dos arquivos era combinado de antemão** ("contrato"), ninguém pisava no trabalho do outro.

Referência: `docs/architecture.md`. Não há banco de dados, nem site, nem login — só scripts que leem e escrevem tabelas Parquet.

### Os "contratos" (arquivos trocados entre as etapas)

| Contrato | Arquivo | O que contém | De → Para |
|---|---|---|---|
| **A1** | `dados/raw/corpus.parquet` | os artigos: id, data, título, texto, fonte, categoria, URL | Coleta → PLN |
| **A2** | `corpus_clean.parquet` + `embeddings.npy` | o texto limpo + os embeddings (as listas de 768 números) | PLN → Modelagem |
| **A3** | `topic_info` / `topic_terms` / `doc_topics` | os tópicos, suas palavras-chave e a qual tópico cada artigo pertence | Modelagem → Scores |
| **A4** | `series.parquet` + `scores.parquet` + `alerts.json` | contagem por dia + as notas de tendência + os alertas | Scores → Dashboard |
| **A5** | `dados/insight/briefings.parquet` | os textos escritos pela IA (nome e "por que sobe" de cada tópico) | IA → Dashboard |

**Três recortes do mesmo corpus (importante desde a coleta multi-fonte):** nem toda etapa usa os mesmos artigos, e isso é proposital e configurável.

| Recorte | Tamanho | Quem usa | Por quê |
|---|---|---|---|
| **Bruto (A1)** | 16.148 | preservação/auditoria | tudo que foi coletado, nada jogado fora |
| **Análise** | 11.225 | PLN, tópicos, chat (RAG) | tira as páginas de catálogo `/produto/` do Canaltech (§6.0) |
| **Temporal** | 6.702 (só Olhar Digital) | séries, scores, alertas | tira o Canaltech, cuja data (`<lastmod>`) é não-confiável (DATA-001, §5 e §7) |

Os dois recortes são controlados por listas no `config.yaml` (`corpus_analise.excluir_url_contendo` e `analise_temporal.fontes_confiaveis`) — esvaziá-las volta ao comportamento "usar tudo". Isso é registrado no `run_manifest.json`, então dá para provar qual recorte gerou cada resultado.

**A identidade dos artigos (`doc_id`):** cada artigo recebe um código único, que é a "impressão digital" (hash) da sua URL. Como a URL nunca muda, o mesmo artigo tem o mesmo id em qualquer computador e em qualquer execução. É esse código que costura tudo: liga o texto → ao embedding → ao tópico → à série → à resposta do chat.

### Ideias de projeto que aparecem o tempo todo (e valem citar na banca)

- **Config num lugar só:** todo número ajustável mora em `config/config.yaml`. Regra do projeto: **nenhum número mágico espalhado pelo código**. Facilita ajustar e, principalmente, *justificar* cada escolha.
- **Calcular antes, mostrar depois:** o dashboard nunca faz conta pesada na hora — ele lê resultados prontos, por isso abre em menos de 5 segundos.
- **Peças opcionais que podem faltar:** a rede neural (Fase 3) e a IA (Fase 5) são **extras**. Se falharem ou não estiverem ligadas, o resto continua funcionando igual. Isso se chama degradação graciosa.
- **Registro do que rodou:** cada execução deixa um "carimbo" (`run_manifest.json`) com data, parâmetros usados e uma impressão digital da config — prova de qual configuração gerou aquele resultado.

### As duas grandes decisões documentadas (ADRs)

- **ADR-001 — a nota de tendência tem 2 camadas.** Uma camada **estatística** (contas simples e confiáveis) e uma camada de **Deep Learning** (a rede neural LSTM). Por quê duas? O curso exigia usar Deep Learning, mas temos só ~4 meses de dados — pouco para uma rede neural sustentar o produto sozinha. Solução: a camada estatística é o **plano garantido**; a rede neural é um **extra** ("detector de surpresa"). Se a rede falha, o produto continua de pé.
- **ADR-002 — a IA roda localmente.** Em vez de usar uma API paga (ChatGPT etc.), rodamos o modelo no nosso computador (Ollama). Motivos: **os dados não saem da máquina** (privacidade/LGPD), **custo zero**, e a demo funciona **sem internet**. E foi feito de forma reversível: trocar para um modelo da nuvem é mudar uma linha de config.

---

## 5. Fase 1 — Coleta (buscar as notícias)

**Em palavras simples:** esta etapa vai aos portais (Olhar Digital e Canaltech), descobre os endereços de todas as notícias dos últimos 4 meses, baixa cada uma, extrai só o texto do artigo e monta uma grande tabela. Ela faz isso de forma "educada" (devagar e se identificando) e **incremental** (só baixa o que ainda não tem).

Módulos: `src/coleta/sitemap.py`, `extract.py`, `canaltech.py`.

### Como funciona, passo a passo

1. **Achar os endereços.** Cada portal publica um *sitemap* (um índice de todas as suas páginas). O SONAR lê esse índice, seleciona só os meses que interessam e junta a lista de URLs de notícias → salva em `urls.parquet`.
2. **Baixar e limpar.** Para cada URL, baixa a página e usa a biblioteca **trafilatura** para extrair só o texto do artigo (jogando fora menu, propaganda, comentários). Monta a tabela de artigos (contrato A1).
3. **Segunda fonte (Canaltech).** Reaproveita o mesmo código, com um detalhe: no Canaltech a data não está na URL, então é pega de um campo do sitemap (`<lastmod>`). No fim, as duas fontes viram uma tabela só, no mesmo formato. **Resultado da coleta completa:** 16.148 artigos (Canaltech 9.446 + Olhar Digital 6.702).

> **Limitação DATA-001 (importante para a banca):** o `<lastmod>` do Canaltech é a data da *última edição* da página, não a da publicação. Na prática, ~54% dos artigos do Canaltech ficaram com a data do dia da coleta, o que **distorce as séries temporais** (um pico artificial no dia da coleta). Por isso o Canaltech entra nos tópicos e no chat, mas é **excluído da análise temporal** — ver §7. Documentado no gate 1.4.

### As decisões e o porquê

| Decisão | Por que assim |
|---|---|
| **Usar o sitemap, não RSS nem API** | O RSS só mostra ~12 notícias do dia — impossível pegar 4 meses. Não existe API pública. O sitemap é o índice completo que o próprio portal publica para o Google. |
| **Coleta educada** (1 requisição/seg, identificando-se, respeitando o robots.txt) | Ética e boas práticas: não sobrecarregar o portal e deixar claro quem somos. Custo: a coleta completa das duas fontes leva ~6h (o Canaltech é lento por rate-limit de 1 req/s somado a ~2s de latência por URL). |
| **Modo incremental** | Baixar tudo toda vez levaria 2h. Baixando só o que é novo, a atualização diária leva minutos. |
| **Guardar em Parquet, não banco de dados** | Para um pipeline que é "arquivo entra, arquivo sai", um banco seria complicação desnecessária. Parquet é rápido, comprimido e preserva os tipos (data continua data). |
| **Corpus congelado** | Para a demonstração da banca dar sempre o mesmo resultado, sem depender de internet. |
| **Tolerância a falha** | Se uma notícia falha ao baixar, ela é pulada com um aviso e a coleta continua — uma página problemática nunca derruba as outras 16 mil. |

### Curiosidades úteis

- Notícias com caracteres especiais na URL (como `m²` ou `CO₂`) às vezes entram num loop de redirecionamento e são puladas — é problema do portal, não do coletor.
- Se o portal mudar o formato das URLs, o coletor para de reconhecê-las e a contagem despenca — os avisos no fim de cada execução tornam isso visível na hora.

---

## 6. Fase 2 — PLN e tópicos (descobrir os assuntos)

**Em palavras simples:** esta etapa pega o texto de cada artigo, limpa, transforma em números que representam o *significado* (embeddings) e depois **agrupa os artigos parecidos** em assuntos (tópicos), dando um nome automático a cada um. É o coração "inteligente" do SONAR — é aqui que ele descobre, sem lista pronta, sobre o que os portais estão falando.

Módulos: `src/pln/clean.py`, `embed.py`, `src/modelagem/topics.py`, `doc_topics.py`. O filtro de catálogo (abaixo) vive em `src/pln/run.py` (`_excluir_catalogo`).

### 6.0 O que entra na análise (filtro de catálogo `/produto/`)

**Em palavras simples:** nem todo o corpus bruto vira "notícia" para os tópicos. Ao carregar as duas fontes, descobrimos que **~4.923 dos 9.446 artigos do Canaltech** eram páginas `/produto/` — catálogos de especificação de celular (listas de "gb", "mp", "mAh", marcas), não jornalismo. Elas poluíam os tópicos com sopa de termos técnicos e boilerplate de navegação (a palavra "entrar" virava nome de tópico).

A solução é um filtro **configurável** em `config/config.yaml` (regra "zero número mágico"):

```yaml
corpus_analise:
  excluir_url_contendo:
    - /produto/
```

Efeito: essas páginas **permanecem no corpus bruto** (contrato A1, preservado), mas ficam **de fora da modelagem** (tópicos, scores e chat). O corpus vai de **16.148 artigos brutos** para **11.225 de análise**. É reversível — esvaziar a lista volta ao comportamento anterior. Os tópicos ficaram mais limpos (a ocorrência de "gb" em tópicos caiu de 58 para 7; "entrar" nos rótulos, de 26 para 0).

### 6.1 Limpeza

Tira do texto o que atrapalha: links, código HTML, emojis — **mas preserva os acentos** (crucial em português). Textos muito curtos (menos de 10 caracteres) são descartados.

### 6.2 Embeddings — transformar texto em números

**Em palavras simples:** um *embedding* é a tradução de um texto para uma lista de números que captura o seu significado. Textos que falam da mesma coisa viram listas parecidas. É o que permite ao computador perceber que "novo iPhone" e "lançamento da Apple" são o mesmo assunto, mesmo sem repetir palavras.

Usamos um modelo **multilíngue** (`paraphrase-multilingual-mpnet-base-v2`) que gera, para cada artigo, uma lista de **768 números**. Por que multilíngue? Porque os modelos mais fortes só existem para inglês; este cobre português com qualidade e roda no nosso computador.

### 6.3 Descobrir e nomear os tópicos (BERTopic)

**Em palavras simples:** o BERTopic olha os embeddings (as listas de 768 números) e junta os artigos que estão "pertinho" uns dos outros — cada aglomerado vira um tópico. Depois, pega as palavras que mais caracterizam cada aglomerado e usa como nome. Ele faz isso em três passos:

1. **Encolher (UMAP):** reduz cada lista de 768 números para só 5, mantendo quem está perto de quem. Necessário porque o passo seguinte se confunde com números demais (a "maldição da dimensionalidade").
2. **Agrupar (HDBSCAN):** forma os grupos por densidade — onde há muitos artigos amontoados, nasce um tópico; artigos soltos ficam "sem tópico" (os *outliers*). **Não precisamos dizer quantos tópicos existem** — ele descobre sozinho (achou 213 no corpus multi-fonte atual).
3. **Nomear (c-TF-IDF):** para cada grupo, acha as palavras que são a "cara" dele — as que aparecem muito ali e pouco nos outros grupos. Essas palavras viram o nome do tópico.

**Por que 21,3% dos artigos ficam "sem tópico"?** Isso é **proposital**. Muitas notícias são genéricas e não pertencem a nenhum assunto quente. Em vez de forçá-las para dentro de um grupo (o que sujaria os tópicos), o HDBSCAN as deixa de lado. Ter uma "lixeira" explícita é uma vantagem.

**Uma armadilha real que resolvemos:** por padrão o BERTopic assume inglês e, ao processar, remove letras acentuadas — o que transformava "missão" em "misso". Tivemos que forçar o modo multilíngue. É o tipo de detalhe que a banca gosta de ouvir.

**Resultado:** 213 tópicos no corpus multi-fonte atual (11.225 artigos de análise). A **coerência** foi validada em **93%** na modelagem original (Story 2.3): ao revisar à mão uma amostra de 30 tópicos, em 28 deles os artigos realmente falavam da mesma coisa (a meta era 70%). A metodologia de validação é a mesma; o número de tópicos cresceu junto com o corpus (era 149 quando só o Olhar Digital estava carregado).

**Por que BERTopic e não o método antigo (LDA)?** O LDA só conta palavras — ele veria "ChatGPT" e "OpenAI" como coisas sem relação, e exige que você diga quantos tópicos quer de antemão. O BERTopic entende significado e descobre o número de tópicos sozinho.

### 6.4 Ligar cada artigo ao seu tópico

Uma tabela final diz, para cada artigo, a qual tópico ele pertence. Se algo der errado nesse cruzamento (um artigo ficar sem data, por exemplo), o sistema **para e avisa** em vez de mascarar o problema — uma lição aprendida numa auditoria interna (ver §10).

---

## 7. Fase 3 — Scores (medir o que está bombando)

**Em palavras simples:** agora que sabemos a qual tópico cada artigo pertence, esta etapa conta **quantos artigos cada tópico teve por dia** e calcula uma **nota de tendência** — o quanto o assunto está acelerando. São duas formas de medir: uma conta estatística simples e confiável (Camada 1) e uma rede neural que detecta "surpresas" (Camada 2).

Módulos: `src/scores/series.py`, `trend_score.py`, `forecast.py`, `backtest.py`. O filtro de fontes temporais vive em `src/scores/run.py` (`_filtrar_fontes_temporais`).

### 7.1 A contagem por dia

Antes de contar, a análise temporal descarta as fontes de **data não-confiável**. Só o **Olhar Digital** (6.702 artigos, data na própria URL) entra nas séries; o Canaltech fica de fora, porque sua data vem do `<lastmod>` do sitemap e cria picos artificiais (limitação DATA-001, §5). O controle é a lista `analise_temporal.fontes_confiaveis: [olhar_digital]` no `config.yaml` — o Canaltech **continua** nos tópicos e no chat, só não conta para tendência.

> **História de honestidade (118 → 0):** quando as duas fontes entravam na análise temporal, o pico artificial do Canaltech gerava **118 alertas de anomalia falsos** e desnormalizava o ranking. Ao restringir as séries às fontes confiáveis, os alertas espúrios caíram para **0** e o ranking normalizou. É o par da história dos "28 → 1" (§7.3): ambos mostram que anomalia estatística exige dados com data correta.

Para cada tópico, monta-se uma linha do tempo: quantos artigos por dia. Dias sem nenhum artigo contam **0** (e não "não existe") — senão as médias ficariam infladas, olhando só os dias movimentados.

### 7.2 Camada 1 — a nota de tendência (Trend Score)

**Em palavras simples:** a nota combina a resposta de três perguntas sobre cada tópico:

1. **Quanto se fala dele?** (volume) — mas usando logaritmo, para um assunto gigante não ganhar sempre só pelo tamanho.
2. **Está crescendo?** (crescimento) — compara a última semana com a semana anterior. Positivo se cresceu, negativo se caiu.
3. **O crescimento é anormal *para ele mesmo*?** (surto) — compara o ritmo atual com a própria história do tópico nos últimos 60 dias. Um tópico que costuma ter 2 artigos/dia e de repente tem 10 está claramente fora do seu normal.

A nota final ≈ **volume × crescimento + surto**. Um tópico grande, crescendo e fora do seu padrão vai para o topo do ranking.

Alguns cuidados embutidos (guardas contra ruído):

- Se um tópico não existia na semana anterior, a conta de "crescimento" daria divisão por zero. Somamos 1 dos dois lados para evitar isso (é a *suavização de Laplace*) — assim um pulinho de 1 para 3 artigos não vira "crescimento infinito".
- Se um tópico tem menos de 5 artigos na semana, ele sai do ranking — com tão poucos dados, qualquer "crescimento" é só sorte.
- Um tópico recém-nascido ganha um selo "🆕 novo" em vez de uma nota inflada.

Essa camada é 100% **estatística e determinística** (sem IA) — roda sempre igual e tem 8 testes automatizados.

### 7.3 Camada 2 — o "detector de surpresa" (rede neural LSTM)

**Em palavras simples:** para cada tópico, uma pequena rede neural (LSTM) aprende o padrão da sua linha do tempo e **prevê quantos artigos deviam sair no dia seguinte**. Se o número real for muito diferente do previsto, isso é uma "surpresa" — e uma surpresa grande vira um **alerta de anomalia**. É a nossa peça de Deep Learning.

Como fazemos isso de forma honesta:

1. **Escondemos o final da série** (o *hold-out*) e treinamos a rede só com o começo. Assim testamos a previsão em dias que ela nunca viu.
2. **Comparamos com um chute bobo** (o *baseline de persistência*: "amanhã = hoje"). Se a rede neural não prevê melhor que esse chute, ela não vale nada — e nós registramos essa comparação abertamente. Isso era uma exigência do projeto (honestidade científica).
3. A **surpresa** (`surprise_z`) mede o quão longe o valor real ficou da previsão da rede, em "tamanhos de erro típico". Passou de 2,5 → **alerta**.

Cuidados: séries curtas demais (menos de ~10 dias) são puladas com aviso, em vez de gerar previsão ruim. E toda essa camada roda "dentro de uma rede de proteção": se qualquer coisa falha, o sistema devolve as notas da Camada 1 intactas.

**Por que uma correção importante:** no começo, tópicos com linha do tempo quase constante geravam 28 "alertas" falsos (porque a variação era quase zero e qualquer coisa parecia anormal). Colocamos um piso mínimo na conta e os falsos alertas caíram para 1 (que era legítimo).

**Por que LSTM e não métodos clássicos (ARIMA/Prophet)?** Três razões: (1) o curso exigia Deep Learning; (2) a LSTM aprende padrões mais complexos; (3) o risco de usar IA com poucos dados é controlado pelo chute-bobo-de-referência e pela rede de proteção.

### 7.4 Backtest — "será que teria funcionado?"

**Em palavras simples:** para provar que o sistema não está só "explicando o passado", nós o testamos **voltando no tempo**: escolhemos uma data passada, escondemos tudo o que veio depois, e vemos se o SONAR teria apontado a tendência certa naquele momento.

Resultado real e convincente: o tópico "lua cheia" ficou **fora do ranking** em três semanas seguidas e **saltou para o 1º lugar exatamente na semana do surto real** de notícias. E o tópico "Artemis/NASA" mostrou a nota **caindo** quando a cobertura esfriou — registramos a queda honestamente, não só os acertos. O cuidado de esconder o futuro antes de qualquer cálculo garante que não há "cola".

---

## 8. Fase 5 — IA generativa (explicar e conversar)

**Em palavras simples:** até aqui o SONAR *mede* tendências, mas não as *explica*. Esta fase adiciona uma IA (um modelo de linguagem, tipo ChatGPT, mas rodando no nosso computador) que faz duas coisas: (A) escreve um resumo "por que esse assunto está subindo" para cada tópico em alta, e (B) responde perguntas sobre as notícias num chat, sempre citando as fontes.

Módulos: `src/common/llm.py`, `src/insight/`, `src/rag/`.

### 8.1 O modelo roda na nossa máquina

Usamos o **Ollama** (programa que roda IAs localmente) com o modelo **qwen2.5:14b**. Nada vai para a nuvem.

**A regra de ouro:** se a IA falhar (travar, dar erro), o código **nunca quebra** — ele simplesmente devolve "vazio" e o resto do SONAR continua. É por isso que a demonstração é segura mesmo se a IA cair.

**Por que esse modelo?** Uma pesquisa nossa mostrou que ele é o **líder em português** num ranking público de modelos (à frente até de versões "mais novas" — provando que "mais novo" não é sempre "melhor"). Ele cabe na nossa GPU de 16 GB usando compressão (quantização). Depois confirmamos com um teste próprio: 100% de confiabilidade e o mais rápido. Um concorrente menor foi eliminado por falhar 1 em cada 3 chamadas.

**Por que local e não uma API paga?** Privacidade (os textos não saem da máquina — importante para o nosso estudo de LGPD), custo zero e demo offline. E é reversível: trocar para a nuvem é mudar uma linha de config, porque o nosso código fala o mesmo "idioma" da OpenAI.

### 8.2 O Analista IA (o "por que sobe")

Para cada tópico em alta, pega os 5 artigos mais representativos e pede à IA dois textos: um **nome curto** para o tópico e um **parágrafo explicando por que ele está subindo** — sempre com base *apenas* nos artigos daquele tópico (para não inventar). Esses textos ficam salvos e versionados (temperatura 0 = sempre o mesmo texto, reprodutível).

**Rede de proteção para rótulos corrompidos (`_label_suspeito`):** de vez em quando o LLM devolve um "nome" estragado — com alfabeto errado (letras cirílicas, por exemplo) ou palavras coladas sem sentido. Quando isso é detectado, o SONAR **descarta** o rótulo da IA e cai no nome gerado pelo c-TF-IDF (as palavras-características do tópico, §6.3). Ou seja: o nome pode perder um pouco de fluência, mas nunca fica ilegível. É mais um exemplo de degradação graciosa.

### 8.3 O chat (RAG) — conversar com as notícias

**Em palavras simples:** RAG é a técnica que faz a IA responder com base nos *nossos* artigos, não no que ela "acha". Quando você faz uma pergunta, o sistema primeiro **busca** os 6 artigos mais parecidos com a pergunta e os entrega ao modelo junto com a pergunta; a IA responde **lendo esses trechos** e **citando** de qual matéria tirou cada afirmação (com link clicável).

Como buscamos os artigos relevantes? Transformamos a pergunta em embedding (com o **mesmo** modelo do corpus — senão os números seriam incompatíveis) e achamos os artigos de embedding mais parecido. Reaproveitamos os embeddings já calculados na Fase 2 — nada é recalculado.

**Como evitamos que a IA invente (alucinação):** quatro defesas — (1) a instrução manda usar *só* os trechos fornecidos; (2) a IA responde mesmo quando os trechos cobrem só **parte** da pergunta (usa o que for relacionado e diz o que falta), e **só recusa** quando *nenhum* trecho tem relação — nesse caso responde "não encontrei isso nos artigos" **sem citação** (testamos com perguntas-pegadinha, como pedir uma receita de bolo — ela recusa corretamente); (3) as **fontes ficam sempre visíveis** para o usuário conferir; (4) temperatura baixa.

> **Ajuste desta sessão:** o prompt do RAG era conservador demais e recusava perguntas que os artigos *parcialmente* respondiam. Foi afrouxado para aproveitar trechos parciais/relacionados, mantendo a recusa apenas para o caso sem nenhuma relação — e a recusa agora sai limpa, sem o marcador de citação `[1]` sobrando.

---

## 9. Fases 4 e 6 — Dashboard

**Em palavras simples:** o dashboard é a tela final que junta tudo. Ele só **mostra** resultados já calculados, por isso abre rápido. Foi construído com Streamlit (permite fazer telas em Python puro).

Módulos: `src/dashboard/app.py`, `graph.py`, `timeseries.py`.

O que a tela mostra, de cima para baixo:
- **Cartões de números** (quantos artigos, quantos tópicos, período coberto).
- **Alertas de anomalia** 🚨 (vindos da rede neural).
- **"🔥 Em Alta"** — o ranking dos assuntos, com selos 🆕 (novo) e 🚨 (anomalia).
- **Detalhe de um tópico** — escolhe-se um tópico e veem-se: a análise da IA (o "por que sobe"), o gráfico ao longo do tempo, as palavras-chave e os artigos originais.
- **Gráfico da linha do tempo semanal.**
- **"Pontes entre tópicos"** — termos que ligam assuntos diferentes.
- **Grafo** — um desenho de termos que aparecem juntos.
- **💬 Chat** — para conversar com as notícias (o RAG).

Detalhes de engenharia que valem citar:
- **Abre rápido** porque não faz conta na hora — só lê arquivos prontos (menos de 5 segundos).
- **Um bug de gráfico corrigido:** o gráfico da linha do tempo estava ilegível porque o programa tratava as datas como texto (criando ~1.900 "categorias") e porque a contagem diária é quase sempre zero. A correção foi tratar como data de verdade e mostrar a contagem **semanal** (o sinal real).
- **Peças que somem sem quebrar:** se a rede neural ou a IA não estiverem disponíveis, o dashboard simplesmente esconde essas seções e mostra o resto normalmente.

---

## 10. Metodologia e histórico

**Como o time trabalhou:** com uma metodologia de "desenvolvimento guiado por histórias" (cada funcionalidade vira uma *story* com critérios claros), e cada story passa por um **portão de qualidade** (revisão que aprova, aprova-com-ressalvas ou reprova). No total, **26 stories entregues** — 21 aprovadas limpas, 4 aprovadas com ressalvas menores, 1 dispensada com justificativa.

| Epic (bloco de trabalho) | O que entregou |
|---|---|
| 1 — Fundação & Coleta | a estrutura do projeto + o coletor das duas fontes |
| 2 — PLN & Tópicos | os tópicos (149 no corpus original; 213 no corpus multi-fonte atual) com 93% de coerência |
| 3 — Trend Score | as duas camadas de nota + o backtest sem "cola" |
| 4 — Dashboard | a tela + o estudo de caso de ética/LGPD |
| 5 — IA Generativa | o Analista IA e o chat com citações |
| 6 — Polimento | tema visual, "pontes", o rebrand para SONAR, correção do gráfico |

**Quatro histórias de honestidade que impressionam banca:**

1. **Uma auditoria interna** da Fase 2 encontrou 13 problemas (uma etapa estava jogando fora a coluna de data, usando filtro de palavras em inglês etc.) — tudo virou uma story de correção. *Lição: revisar o próprio trabalho pega erros que passariam batido.*
2. **Os 28 alertas falsos** que viraram 1 quando entendemos o problema estatístico (variação quase zero). *Lição: casos extremos de estatística precisam de proteção.*
3. **"O mais novo não é o melhor":** o modelo de IA mais recente perdeu para um anterior nos testes de português. *Lição: testar no seu próprio caso vale mais que seguir o hype.*
4. **Os 118 alertas falsos → 0** ao dobrar o corpus: a segunda fonte (Canaltech) trouxe datas não-confiáveis (`<lastmod>`) que criavam picos artificiais. Em vez de mascarar, isolamos a causa e excluímos essa fonte só da análise temporal — mantendo-a nos tópicos e no chat. *Lição: mais dados só ajudam se a qualidade (aqui, a data) for confiável; a solução deve ser cirúrgica e reversível.*

---

## 11. Q&A de banca

### Sobre o produto
- **"Por que não usar o Google Trends?"** — Ele mede o que as pessoas *pesquisam*, não o que os jornalistas *escrevem*; não separa os assuntos automaticamente em português técnico; e só mostra uma curva, sem explicar. O SONAR agrupa sozinho, mede a aceleração e explica o porquê com fontes.
- **"Como sei que é tendência de verdade e não ruído?"** — Há proteções (tópico precisa de pelo menos 5 artigos, tratamento de casos extremos), duas medições independentes, e a tela mostra as evidências (gráfico, palavras, artigos) para você mesmo julgar.
- **"O sistema já acertou algo real?"** — Sim, no backtest: o tópico "lua cheia" saltou para o 1º lugar do ranking exatamente na semana do surto real de notícias, tendo ficado fora nas três semanas anteriores.

### Sobre a parte técnica
- **"O que é um embedding?"** — A tradução de um texto para uma lista de números que representa o significado; textos parecidos viram listas parecidas. É o que deixa o computador perceber que dois artigos falam da mesma coisa.
- **"O que é c-TF-IDF?"** — O método que dá nome aos tópicos: acha as palavras que são a "cara" de cada grupo — frequentes nele e raras nos outros.
- **"O que é o surprise_z?"** — O tamanho da "surpresa": o quanto o número real de artigos de um dia ficou longe do que a rede neural previu, medido em tamanhos de erro típico. Grande demais → alerta.
- **"Por que BERTopic e não LDA?"** — O LDA só conta palavras (não entende significado) e exige dizer quantos tópicos existem. O BERTopic entende significado e descobre o número sozinho — e deu 93% de coerência.
- **"O que é RAG?"** — A técnica do chat: buscar os trechos relevantes dos nossos artigos e mandar junto com a pergunta, para a IA responder com base neles e citar a fonte — em vez de responder "de cabeça" e arriscar inventar.
- **"Por que a IA roda localmente e não numa API paga?"** — Privacidade (nada sai da máquina), custo zero e demo offline. E é reversível: uma linha de config troca para a nuvem.
- **"Por que LSTM e não ARIMA?"** — O curso exigia Deep Learning; a LSTM aprende padrões mais ricos; e o risco de usar IA com poucos dados é controlado por um baseline de comparação obrigatório.
- **"Como garantem que o backtest não 'cola'?"** — Escondemos tudo o que veio depois da data de teste **antes** de qualquer cálculo. Há até um teste automatizado que verifica isso.

### Sobre o processo
- **"Como 4 pessoas trabalharam sem conflito?"** — Cada um cuidou de uma etapa, e o formato dos arquivos trocados entre etapas era combinado ("contrato"). Ninguém mexia no arquivo do outro.
- **"E se a IA cair na apresentação?"** — Nada quebra: a tela detecta e esconde só a parte da IA; os textos já gerados ficam salvos. A parte medida (tópicos, ranking) continua.
- **"Como reproduzo a demo?"** — `poetry install`, depois `poetry run sonar`, depois `poetry run streamlit run src/dashboard/app.py`.

---

## 12. Limitações e mitigações

Ser transparente sobre os limites é ponto forte na banca. Os principais:

| Limitação | Como lidamos |
|---|---|
| No Canaltech, a data vem do `<lastmod>` do sitemap (muda quando o artigo é editado) e concentra ~54% dos artigos no dia da coleta — distorceria as séries (limitação DATA-001) | **Resolvido:** o Canaltech é excluído da análise temporal via `analise_temporal.fontes_confiaveis: [olhar_digital]`. Ele permanece nos tópicos e no chat; só não conta para tendência (§7). Reversível pelo config. |
| O Canaltech traz muitas páginas de catálogo `/produto/` (specs de celular), que não são notícia e poluiriam os tópicos | **Resolvido:** filtro `corpus_analise.excluir_url_contendo: [/produto/]` tira ~4.923 páginas da modelagem (§6.0); elas seguem no corpus bruto (A1). Reversível. |
| O LLM às vezes devolve um rótulo de tópico corrompido (alfabeto errado, palavras coladas) | Detecção `_label_suspeito` descarta o rótulo suspeito e usa o nome do c-TF-IDF; o nome nunca fica ilegível (§8.2) |
| Algumas palavras vazias ("portanto", "além disso") escapam do filtro e sujam poucos dos 213 tópicos | Os nomes gerados pela IA (Fase 5) corrigem isso na exibição |
| A coleta completa das duas fontes leva ~6h (Canaltech lento) | É opcional; o modo incremental atualiza em minutos e o demo usa o corpus congelado |
| Temos só ~4 meses de dados — pouco para a rede neural | Proteções contra falso alerta + a coleta vai alongando a série com o tempo |
| A avaliação "às cegas" da qualidade dos textos da IA foi dispensada | A escolha do modelo se apoiou em métricas objetivas; a planilha está pronta para uso futuro |
| O chat não lembra das perguntas anteriores (cada pergunta é independente) | Escolha consciente; perguntas autocontidas funcionam bem |

---

*Este guia foi escrito a partir de uma revisão completa do código, dos requisitos (PRD), das decisões de arquitetura (ADRs), das 26 stories e dos relatórios de qualidade, em 2026-07-10. Para o resumo executivo (o que o SONAR faz e suas capacidades), veja o [Relatório do Projeto](../relatorio-projeto.md).*
