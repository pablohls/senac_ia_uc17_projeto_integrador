"""Coletor de URLs datadas a partir do sitemap do Olhar Digital (Story 1.2).

Por que sitemap e não RSS: o RSS só expõe ~12 itens do dia, sem histórico. O
sitemap do portal é organizado **por mês** (``sitemap_post_AAAA-MM.xml``), o que
nos dá o índice histórico completo do corpus.

Arquitetura do módulo (importante para os testes):
  - Funções **determinísticas** (sem rede) — `meses_alvo`, `parse_artigo`,
    `construir_dataframe` — são o coração testável (ver `tests/test_sitemap.py`).
  - Funções de **rede** — `baixar`, `listar_sitemaps_mensais`, `listar_urls` —
    isolam o acesso HTTP e são validadas manualmente (NFR4: User-Agent + pausa).

Saída: DataFrame com o schema ``url, data, categoria, fonte`` persistido em
``dados/raw/urls.parquet`` (consumido pela Story 1.3).
"""

from __future__ import annotations

import re
import time
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import requests
from lxml import etree

from src.common.config import Config, SitemapParams, load_config
from src.common.io import salvar_parquet

# Identificador da fonte no schema de saída.
FONTE = "olhar_digital"
FONTE_CANALTECH = "canaltech"

# Padrão da URL de artigo do Canaltech: /categoria/slug/ (data NÃO está na URL —
# vem do <lastmod>). Ex.: https://canaltech.com.br/apps/whatsapp-vai-exigir.../
CANALTECH_ARTIGO_RE = re.compile(r"canaltech\.com\.br/([^/]+)/([^/]+)")

# Namespace padrão dos sitemaps (protocolo sitemaps.org 0.9).
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# Caminho de saída (intermediário, consumido pela Story 1.3).
CAMINHO_SAIDA = Path("dados/raw/urls.parquet")

# Padrão da URL de artigo: /AAAA/MM/DD/categoria/slug/
# Ex.: https://olhardigital.com.br/2026/06/06/ciencia-e-espaco/titulo-do-artigo/
URL_ARTIGO_RE = re.compile(
    r"olhardigital\.com\.br/(\d{4})/(\d{2})/(\d{2})/([^/]+)/([^/]+)/?$"
)

# Padrão do nome de um sitemap mensal: sitemap_post_AAAA-MM(.xml | _N.xml)
SITEMAP_MENSAL_RE = re.compile(r"sitemap_post_(\d{4}-\d{2})")


# ---------------------------------------------------------------------------
# Funções determinísticas (sem rede) — núcleo testável
# ---------------------------------------------------------------------------
def meses_alvo(n: int, hoje: date | None = None) -> list[str]:
    """Retorna os últimos ``n`` rótulos ``'AAAA-MM'`` (incluindo o mês corrente).

    Args:
        n: quantidade de meses para trás.
        hoje: data de referência (injetável para testes; default = agora UTC).

    Returns:
        Lista de rótulos ``'AAAA-MM'`` do mais recente ao mais antigo.
    """
    ref = hoje or datetime.now(UTC).date()
    rotulos: list[str] = []
    ano, mes = ref.year, ref.month
    for _ in range(n):
        rotulos.append(f"{ano:04d}-{mes:02d}")
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
    return rotulos


def parse_artigo(url: str) -> tuple[date, str] | None:
    """Deriva ``(data, categoria)`` da URL de um artigo.

    Esta é a função determinística central da story: a data e a categoria vêm
    embutidas no próprio caminho da URL, sem precisar baixar a página.

    Args:
        url: URL completa do artigo.

    Returns:
        Tupla ``(date, categoria)`` se a URL casar com o padrão de artigo e a
        data for válida; ``None`` caso contrário (ex.: página institucional).
    """
    m = URL_ARTIGO_RE.search(url)
    if not m:
        return None
    ano, mes, dia, categoria, _slug = m.groups()
    try:
        d = date(int(ano), int(mes), int(dia))
    except ValueError:
        # Data impossível na URL (ex.: /2026/13/40/...) — descarta.
        return None
    return d, categoria


def construir_dataframe(
    urls: list[str], categorias: list[str] | None = None
) -> pd.DataFrame:
    """Monta o DataFrame final a partir de uma lista de URLs (sem rede).

    Faz parse de cada URL, descarta as que não são artigos, aplica filtro
    opcional por categoria e **deduplica por URL**. Centraliza aqui a lógica
    determinística para que dedup + filtro + schema sejam testáveis sem rede.

    Args:
        urls: URLs candidatas (de um ou mais sitemaps mensais).
        categorias: filtro opcional; se vazio/``None``, mantém todas.

    Returns:
        DataFrame com colunas ``url, data, categoria, fonte`` (``fonte`` como
        ``category``), sem URLs repetidas.
    """
    filtro = set(categorias or [])
    registros: list[dict] = []
    vistos: set[str] = set()

    for url in urls:
        if url in vistos:
            continue
        info = parse_artigo(url)
        if info is None:
            continue
        data_artigo, categoria = info
        if filtro and categoria not in filtro:
            continue
        vistos.add(url)
        registros.append(
            {"url": url, "data": data_artigo, "categoria": categoria, "fonte": FONTE}
        )

    df = pd.DataFrame(registros, columns=["url", "data", "categoria", "fonte"])
    if not df.empty:
        df["fonte"] = df["fonte"].astype("category")
    return df


def urls_de_xml(xml_bytes: bytes) -> list[str]:
    """Extrai o texto de todas as tags ``<loc>`` de um XML de sitemap.

    Serve tanto para o index (``<sitemap><loc>``) quanto para os mapas mensais
    (``<url><loc>``). O parse é tolerante a XML malformado (``recover=True``).

    Args:
        xml_bytes: conteúdo bruto do XML.

    Returns:
        Lista das URLs encontradas nas tags ``<loc>``.
    """
    raiz = etree.fromstring(xml_bytes, parser=etree.XMLParser(recover=True))
    return [(loc.text or "").strip() for loc in raiz.findall(".//sm:loc", SITEMAP_NS)]


# ---------------------------------------------------------------------------
# Funções de rede — validadas manualmente (NFR4)
# ---------------------------------------------------------------------------
def baixar(url: str, user_agent: str, timeout: int = 30) -> bytes:
    """GET simples com ``User-Agent`` definido (coleta educada — NFR4).

    Args:
        url: endereço a baixar.
        user_agent: identificação enviada ao servidor.
        timeout: tempo máximo, em segundos.

    Returns:
        Corpo da resposta em bytes.

    Raises:
        requests.HTTPError: se o status não for 2xx.
    """
    resp = requests.get(url, headers={"User-Agent": user_agent}, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def listar_sitemaps_mensais(params: SitemapParams) -> list[str]:
    """Lê o sitemap index e devolve os mapas mensais dos últimos N meses.

    Args:
        params: parâmetros do coletor (index_url, meses, user_agent).

    Returns:
        URLs dos sitemaps mensais selecionados, do mais recente ao mais antigo.
    """
    alvos = set(meses_alvo(params.meses))
    selecionados: list[str] = []
    for url in urls_de_xml(baixar(params.index_url, params.user_agent)):
        m = SITEMAP_MENSAL_RE.search(url)
        if m and m.group(1) in alvos:
            selecionados.append(url)
    return sorted(selecionados, reverse=True)


def listar_urls(config: Config) -> pd.DataFrame:
    """Coleta todas as URLs de artigos datadas dos últimos N meses.

    Orquestra o fluxo de rede: baixa o index, percorre os sitemaps mensais,
    junta todas as ``<loc>`` e delega o parse/dedup/filtro para
    :func:`construir_dataframe`. Respeita o rate-limit entre requisições (NFR4).

    Args:
        config: configuração validada do projeto.

    Returns:
        DataFrame ``url, data, categoria, fonte`` sem duplicatas.
    """
    params = config.coleta.sitemap
    sitemaps = listar_sitemaps_mensais(params)

    todas_urls: list[str] = []
    for i, sm_url in enumerate(sitemaps):
        try:
            todas_urls.extend(urls_de_xml(baixar(sm_url, params.user_agent)))
        except requests.RequestException as e:
            # Um mês indisponível não derruba a coleta inteira.
            print(f"[!] Falha em {sm_url}: {e}")
        if i < len(sitemaps) - 1:
            time.sleep(params.rate_limit_s)

    return construir_dataframe(todas_urls, params.categorias)


# ---------------------------------------------------------------------------
# Segunda fonte: Canaltech (Story 1.4) — estrutura diferente do Olhar Digital
# ---------------------------------------------------------------------------
# O Canaltech difere em dois pontos: (a) a data vem do <lastmod> do sitemap, não
# da URL; (b) os shards (geral-N.xml) não são mensais e cobrem todo o histórico.
# Por isso filtramos a janela recente por `lastmod` em vez de selecionar sitemaps.
def parse_categoria_canaltech(url: str) -> str | None:
    """Deriva a ``categoria`` da URL do Canaltech (1º segmento do path).

    Args:
        url: URL do artigo (``canaltech.com.br/{categoria}/{slug}/``).

    Returns:
        A categoria (1º segmento) para URLs de artigo (≥2 segmentos); ``None``
        para páginas de seção/home (que não casam o padrão).
    """
    m = CANALTECH_ARTIGO_RE.search(url)
    return m.group(1) if m else None


def data_corte(meses: int, hoje: date | None = None) -> date:
    """Primeiro dia do mês mais antigo da janela de ``meses`` (determinístico).

    Usado para filtrar artigos do Canaltech por ``lastmod`` (ex.: ``meses=4`` em
    junho/2026 → corte ``2026-03-01``).

    Args:
        meses: tamanho da janela em meses (inclui o mês corrente).
        hoje: data de referência (injetável para testes; default = agora UTC).

    Returns:
        ``date`` do 1º dia do mês mais antigo da janela.
    """
    ref = hoje or datetime.now(UTC).date()
    total = (ref.year * 12 + (ref.month - 1)) - (meses - 1)
    ano, mes0 = divmod(total, 12)
    return date(ano, mes0 + 1, 1)


def _parse_lastmod(valor: str) -> date | None:
    """Extrai a ``date`` de um ``<lastmod>`` ISO (``2026-06-11T10:40:12-03:00``)."""
    try:
        return date.fromisoformat((valor or "")[:10])
    except (ValueError, TypeError):
        return None


def construir_urls_canaltech(
    registros: list[tuple[str, str]], corte: date
) -> pd.DataFrame:
    """Monta o DataFrame de URLs do Canaltech a partir de ``(loc, lastmod)`` (sem rede).

    Filtra pela janela (``lastmod >= corte``), deriva a categoria da URL, deduplica
    por ``url`` e produz o **mesmo schema** da Story 1.2 (``url, data, categoria,
    fonte``) para reuso direto pela extração de texto (1.3).

    Args:
        registros: lista de ``(url, lastmod_iso)`` dos shards.
        corte: data mínima de publicação (do :func:`data_corte`).

    Returns:
        DataFrame ``url, data, categoria, fonte`` (``fonte = "canaltech"``).
    """
    linhas: list[dict] = []
    vistos: set[str] = set()
    for loc, lastmod in registros:
        if loc in vistos:
            continue
        d = _parse_lastmod(lastmod)
        if d is None or d < corte:
            continue
        categoria = parse_categoria_canaltech(loc)
        if categoria is None:
            continue  # página de seção/home — não é artigo
        vistos.add(loc)
        linhas.append({"url": loc, "data": d, "categoria": categoria, "fonte": FONTE_CANALTECH})

    df = pd.DataFrame(linhas, columns=["url", "data", "categoria", "fonte"])
    if not df.empty:
        df["fonte"] = df["fonte"].astype("category")
    return df


def registros_canaltech_de_xml(xml_bytes: bytes) -> list[tuple[str, str]]:
    """Extrai ``(loc, lastmod)`` de cada ``<url>`` de um shard do Canaltech.

    Diferente de :func:`urls_de_xml` (só ``<loc>``), aqui também lemos o
    ``<lastmod>`` — pois é dele que vem a data do artigo.

    Args:
        xml_bytes: conteúdo bruto do shard (pode ser grande — usa ``huge_tree``).

    Returns:
        Lista de ``(url, lastmod_iso)``.
    """
    raiz = etree.fromstring(
        xml_bytes, parser=etree.XMLParser(recover=True, huge_tree=True)
    )
    saida: list[tuple[str, str]] = []
    for u in raiz.findall(".//sm:url", SITEMAP_NS):
        loc = u.findtext("sm:loc", namespaces=SITEMAP_NS)
        if not loc:
            continue
        lastmod = u.findtext("sm:lastmod", namespaces=SITEMAP_NS) or ""
        saida.append((loc.strip(), lastmod.strip()))
    return saida


def listar_urls_canaltech(config: Config) -> pd.DataFrame:
    """Lista as URLs datadas do Canaltech na janela dos últimos N meses.

    Lê o index → shards, extrai ``(loc, lastmod)`` de cada shard, filtra pela
    janela e monta o DataFrame no schema da Story 1.2. Respeita rate-limit (NFR4).

    Args:
        config: configuração validada (requer ``coleta.canaltech``).

    Returns:
        DataFrame ``url, data, categoria, fonte`` (``fonte = "canaltech"``).
    """
    params = config.coleta.canaltech
    if params is None:
        raise ValueError("config.coleta.canaltech ausente — defina a seção no config.yaml.")
    corte = data_corte(params.meses)

    shards = urls_de_xml(baixar(params.index_url, params.user_agent))
    registros: list[tuple[str, str]] = []
    for i, shard in enumerate(shards):
        try:
            registros.extend(registros_canaltech_de_xml(baixar(shard, params.user_agent)))
        except requests.RequestException as e:
            print(f"[!] Falha em {shard}: {e}")
        if i < len(shards) - 1:
            time.sleep(params.rate_limit_s)

    return construir_urls_canaltech(registros, corte)


def main() -> None:
    """Executa a coleta com base na config e persiste em ``dados/raw/urls.parquet``."""
    config = load_config()
    df = listar_urls(config)
    destino = salvar_parquet(df, CAMINHO_SAIDA)
    print(f"[✓] {len(df)} URLs datadas salvas em {destino}")
    if not df.empty:
        print(f"    Período: {df['data'].min()} → {df['data'].max()}")
        print(f"    Categorias: {df['categoria'].nunique()} distintas")


if __name__ == "__main__":
    main()
