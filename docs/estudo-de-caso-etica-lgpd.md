# Estudo de Caso & Ética/LGPD — TrendRadar (Story 4.4)

## Parte 1 — Estudo de caso: uma tendência detectada

> **Nota:** os números desta seção são preenchidos a partir do backtest
> (`docs/qa/validacao_backtest.md`, Story 3.4) executado sobre o corpus
> congelado. Ver metodologia lá descrita: cortes no tempo sem vazamento
> de futuro.

_(seção preenchida após a execução do pipeline sobre o corpus completo —
tópico analisado, evolução do trend_score entre os cortes, figura da série
temporal e narrativa do evento real por trás do surto)_

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
