# Estudo de Caso & Ética/LGPD — TrendRadar (Story 4.4)

## Parte 1 — Estudo de caso: uma tendência detectada

> **Fonte dos números:** backtests da Story 3.4 sobre o corpus congelado
> (6.423 artigos, Olhar Digital, mar–jul/2026) — `docs/qa/validacao_backtest.md`
> e `docs/qa/backtest-artemis-t0.md`. Metodologia: para cada corte T, os scores
> são recalculados usando **apenas** dados com `data <= T` (sem vazamento de
> futuro). Figura interativa: `docs/img/estudo-caso-series.html`.

### Caso principal — T139 "lua cheia": detecção a partir do silêncio

Na primeira semana de julho/2026, o portal publicou uma onda de artigos sobre a
lua cheia do mês (a "Lua do Cervo", evento astronômico datado e verificável).
O backtest congela o sistema em 4 momentos e observa o que ele teria dito:

| Corte (T) | Artigos na janela (R) | growth | trend_score | Leitura |
|---|---|---|---|---|
| 15/06 | 0 | 1,0 | −inf | tópico mudo — fora do ranking (guarda `n_min`) |
| 22/06 | 0 | 1,0 | −inf | idem |
| 29/06 | 0 | 1,0 | −inf | idem |
| **06/07** | **7** | **8,0×** | **8,07** | **1º lugar do ranking — tendência sinalizada** |

O sistema ficou **corretamente em silêncio** enquanto não havia cobertura (a
guarda de suporte mínimo impede que ruído entre no ranking) e sinalizou o
assunto **na semana em que o surto aconteceu**, colocando-o no topo. É o
comportamento desejado de um radar de tendências: não gritar antes, não
atrasar depois.

### Caso complementar — T0 "artemis missão nasa": o score acompanha o ciclo da notícia

O maior tópico do corpus (318 artigos) cobre a missão **Artemis 2** da NASA —
evento real com tripulação, amplamente noticiado. Aqui o backtest mostra a
outra face do algoritmo — o score **desce** quando a cobertura esfria e
**volta a subir** com a nova onda de notícias:

| Corte (T) | R | growth | trend_score | Leitura |
|---|---|---|---|---|
| 15/06 | 20 | 1,75× | 1,86 | cobertura aquecida |
| 22/06 | 7 | 0,38× | −2,01 | ciclo esfria — score negativo (queda) |
| 29/06 | 5 | 0,75× | −0,51 | estabilização em baixa |
| 06/07 | 16 | 2,83× | 3,35 | nova onda de notícias — score sobe |

**Por que isso importa:** o trend_score não mede "tamanho" do assunto, mede
**aceleração** — um tópico grande e estável não é tendência; um tópico
acelerando é. Os dois casos juntos mostram as duas propriedades.

### Achado honesto do processo de validação

A primeira execução do backtest expôs um defeito real: em séries quase
constantes, o desvio dos resíduos (σ) tendia a zero e o score de surpresa da
Camada 2 explodia (z > 300), marcando "anomalia" em cortes onde **nada havia
acontecido** (R = 0). A correção — piso `sigma_min = 1.0` documentado em
`config.yaml` — derrubou os alertas de 28 para **1** (T35 "iphone apple":
3 artigos reais vs 0,34 previstos, z = 2,66 > k = 2,5, um pico legítimo).
Este é exatamente o risco de **alarme falso** discutido na Parte 2, detectado
e mitigado pela própria validação.

## Parte 2 — Ética e LGPD

### 2.1 Natureza dos dados: públicos e editoriais

O TrendRadar coleta **exclusivamente conteúdo editorial público** — notícias
publicadas abertamente por portais de tecnologia (Olhar Digital e Canaltech).
Não há coleta de dados de usuários, comentários, perfis ou qualquer conteúdo
de acesso restrito.

### 2.2 Coleta responsável (NFR4)

- **Descoberta via sitemap oficial:** as URLs vêm dos sitemaps que os próprios
  portais publicam para indexação — o mesmo mecanismo usado por buscadores.
- **Identificação transparente:** todas as requisições enviam o User-Agent
  `TrendRadar/0.1 (projeto integrador IA; coleta academica)`, permitindo que
  os portais identifiquem e, se quiserem, bloqueiem o robô.
- **Rate-limiting educado:** ~1 requisição por segundo (`rate_limit_s: 1.0`
  em `config/config.yaml`), sem paralelismo agressivo — a coleta completa
  leva ~2h justamente para não sobrecarregar os servidores.
- **Dataset congelado:** a coleta é feita uma única vez e o corpus é
  congelado (contrato A1); o sistema não martela as fontes repetidamente.

### 2.3 LGPD e dados pessoais (PII)

O pipeline **não coleta nem armazena dados pessoais**:

- Os campos armazenados são: `doc_id` (hash da URL), `data`, `titulo`,
  `texto` (corpo editorial), `fonte`, `categoria` e `url` — todos referentes
  à **matéria jornalística**, não a pessoas.
- Nomes citados em notícias (executivos, autoridades) são informação
  jornalística de interesse público já publicada pela fonte — o TrendRadar
  não cruza, enriquece nem perfila esses dados (art. 7º, LGPD — legítimo
  interesse/uso acadêmico; art. 4º, I — fins exclusivamente acadêmicos).
- Não há cadastro de usuários no dashboard; nenhum dado de quem usa o
  sistema é coletado.
- **Anonimização estrutural:** o `doc_id = SHA-1(url)[:16]` referencia
  artigos, nunca indivíduos; as agregações (tópicos, séries, scores) operam
  em nível de assunto.

### 2.4 Risco de alarme falso (falso positivo)

Nenhum detector de tendências é perfeito. Um surto estatístico pode ser ruído
(ex.: cobertura repetida de um mesmo evento) e não uma tendência real. Um
falso positivo poderia induzir decisões erradas em quem consome o dashboard.

**Mitigações implementadas:**

| Mitigação | Onde | Efeito |
|---|---|---|
| Suporte mínimo `n_min = 5` | Camada 1 (ADR-001) | Tópico com poucos documentos não entra no ranking |
| Suavização de Laplace `alpha = 1.0` | Camada 1 | Crescimento sobre base minúscula não explode o score |
| Duas camadas independentes | L1 estatística + L2 LSTM | Anomalia (🚨) exige surpresa além do previsto pelo modelo, não só crescimento |
| Badge "novo" (🆕) separado | Camada 1 | Tópico recém-nascido é sinalizado como tal, não mascarado de tendência madura |
| Backtest honesto | Story 3.4 | A validação relata o que o sistema FEZ, inclusive quando o score não sobe |

**Mitigação de processo:** o dashboard exibe as evidências (série temporal,
termos, artigos-fonte) para que o usuário **verifique a tendência na fonte**
antes de agir — o sistema recomenda investigação, não conclusão.

### 2.5 Limitações declaradas

- **Duas fontes** de notícias — o "radar" enxerga o recorte editorial delas,
  não "a internet".
- **Janela histórica de ~4 meses** — tendências de ciclo longo ficam fora do
  alcance do horizonte H do ADR-001.
- **Datas do Canaltech via `<lastmod>`** do sitemap — conteúdo antigo
  atualizado pode aparecer com data recente (viés conhecido, documentado na
  Story 1.4).

## Parte 3 — Reprodução do demo (3 comandos)

```bash
poetry install                                  # 1. ambiente isolado + dependências
poetry run trendradar                           # 2. pipeline offline (PLN → tópicos → scores)
poetry run streamlit run src/dashboard/app.py   # 3. dashboard de tendências
```

Detalhes e pré-requisitos: ver [README.md](../README.md).
