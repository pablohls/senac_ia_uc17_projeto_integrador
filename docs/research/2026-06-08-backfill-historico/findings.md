# Pesquisa de Viabilidade: Backfill Histórico de Notícias (SONAR)

> **Autor:** @analyst (Atlas) | **Data:** 2026-06-08
> **Objetivo:** resolver o Risco nº 1 do brief — RSS não tem profundidade histórica para a série temporal.
> **Método:** testes empíricos ao vivo nas APIs/endpoints (não só busca).

---

## 🔴 Problema confirmado empiricamente

O RSS do Olhar Digital (`/rss`) retornou **apenas 12 itens, todos do mesmo dia** (08/06/2026, janela de ~3h). RSS é **janela rolante** — sem histórico. Coletar ao vivo por 2 semanas daria, no máximo, ~2 semanas de dados, insuficiente para detectar tendências.

---

## ✅ Solução recomendada (validada): Sitemaps datados dos portais

### Opção PRIMÁRIA — Sitemap mensal do Olhar Digital ⭐

- **Endpoint:** `https://olhardigital.com.br/sitemap.xml` → é um **sitemap index** com sub-sitemaps **organizados por mês**: `sitemap_post_2026-06.xml`, `sitemap_post_2026-05_1.xml`, etc. (460 entradas no índice, voltando anos).
- **Volume confirmado:** o sitemap `2026-05` parte 1 sozinho tem **950 URLs de artigos datados** → ~1.500–2.000 artigos/mês.
- **Bônus:** a própria URL codifica **data e categoria**:
  `https://olhardigital.com.br/2026/06/06/ciencia-e-espaco/terras-raras-...`
  → dá pra filtrar por categoria (ex.: `ciencia-e-espaco`) sem nem abrir o artigo.
- **Implicação:** ~50–70 artigos/dia → **granularidade diária da série temporal é viável** (resolve a dúvida de granularidade do brief).
- **Status:** ✅ legal, estável, datado, sem API key.

### Opção SECUNDÁRIA — Sitemap do Canaltech

- **Endpoint:** declarado no `robots.txt` em `https://static.canaltech.com.br/smap/geral.xml` (o caminho padrão `/sitemap.xml` dá 404 — por isso não achavam).
- É um **sitemap index** (`geral-1.xml` … `geral-4.xml`). Serve como **segunda fonte** para enriquecer o corpus e validar tendências cruzando portais.

### Opção COMPLEMENTAR — GDELT DOC 2.0 API

- Suporta **português brasileiro** (1 das 65 línguas), janela **rolante de 3 meses** grátis, filtro por domínio (`domainis:canaltech.com.br`) e por língua (`sourcelang:por`).
- Endpoint: `https://api.gdeltproject.org/api/v2/doc/doc?query=...&mode=artlist&format=json`
- **Cuidado:** rate-limit agressivo (retornou HTTP 429 em requisições próximas). Usar com **espaçamento ≥ 5s entre chamadas**.
- **Uso ideal:** enriquecer com mais portais pt-BR de uma vez e fazer validação cruzada — não como fonte única.

---

## ❌ Opções descartadas

- **Wayback Machine do RSS:** só **2 capturas** do feed em 3 meses (ambas em 27/05) — não arquiva o RSS com regularidade. Inviável para reconstruir stream.
- **Apenas RSS ao vivo:** ~12 itens/dia, zero histórico.
- **GDELT BigQuery (dump completo):** histórico total existe, mas o GKG de um ano sozinho passa de 2,5 TB — overkill para o escopo/prazo.

---

## 🛠️ Receita de implementação do backfill (Olhar Digital)

1. **GET** o sitemap index → listar os `sitemap_post_AAAA-MM*.xml` dos últimos **N meses** (sugestão: 4–6 meses → ~6k–12k artigos).
2. Para cada sitemap mensal → extrair `<loc>` (URLs) e `<lastmod>` (datas).
3. **Filtrar por categoria** pela própria URL, se quiser restringir o nicho.
4. **Raspar o texto** de cada artigo com `trafilatura` ou `newspaper3k` (respeitar robots.txt, rate-limit ~1 req/s).
5. **Persistir** `data, título, texto, fonte, categoria, url` em CSV/Parquet → **dataset congelado** (reprodutível para o demo).
6. (Opcional) Repetir para o Canaltech e/ou GDELT para um corpus multi-fonte.

> Bibliotecas: `requests`/`feedparser`, `lxml`/`BeautifulSoup` (parse sitemap), `trafilatura` (extração de texto limpo), `pandas` (persistência).

---

## 🎯 Impacto no projeto

- **Risco nº 1 (histórico) → RESOLVIDO.** Há fonte legal e datada com profundidade de meses/anos.
- **Granularidade diária viável** (~50–70 artigos/dia só no Olhar Digital).
- Corpus de **6k–12k documentos datados** em poucos dias de coleta → suficiente para HDBSCAN com clusters significativos e para séries temporais por tópico.
- **Ressalva remanescente:** mesmo com bom histórico, a série por tópico ainda pode ser curta para LSTM — manter a comparação com baseline (já previsto no brief).

## Fontes

- [GDELT DOC 2.0 API](https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/) · [GDELT Project](https://www.gdeltproject.org/)
- Testes ao vivo: `olhardigital.com.br/sitemap.xml`, `static.canaltech.com.br/smap/geral.xml`, `olhardigital.com.br/rss`, Wayback CDX API.
