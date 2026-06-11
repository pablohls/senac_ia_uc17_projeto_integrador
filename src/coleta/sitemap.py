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
