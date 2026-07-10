"""Extração de texto dos artigos → dataset congelado A1 (Story 1.3).

A Story 1.2 produziu a **lista de URLs** (`dados/raw/urls.parquet`). Aqui visitamos
cada URL, extraímos `título` e `texto` limpos com `trafilatura`, e montamos o
**artefato A1** (`dados/raw/corpus.parquet`) — a base de **todas** as fases
seguintes (PLN, modelagem, séries, dashboard).

Decisões de contrato (ver `docs/architecture.md` — A1):
  - `doc_id` = hash **estável e imutável** da URL → chave primária que atravessa
    todo o pipeline. Gerada **só** da URL (nunca de algo que mude entre execuções).
  - Garantias: deduplicado por `url`; `texto` não-vazio; falhas logadas e excluídas
    (um artigo problemático nunca derruba o lote — AC2).

Arquitetura do módulo (importante para os testes):
  - **Determinístico** (sem rede): `gerar_doc_id`, `montar_corpus`.
  - **Rede** (validado em amostra): `extrair_um`, `carregar_robots`, `extrair_artigos`.
"""

from __future__ import annotations

import hashlib
import logging
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pandas as pd
import trafilatura

from src.coleta.sitemap import FONTE, baixar
from src.common.config import Config, load_config
from src.common.io import atualizar_manifest, ler_parquet, salvar_parquet

logger = logging.getLogger(__name__)

# Entrada (Story 1.2) e saída (artefato A1).
CAMINHO_URLS = Path("dados/raw/urls.parquet")
CAMINHO_CORPUS = Path("dados/raw/corpus.parquet")

# Ordem canônica das colunas do schema A1 (contrato — ver architecture.md).
COLUNAS_A1 = ["doc_id", "data", "titulo", "texto", "fonte", "categoria", "url"]


# ---------------------------------------------------------------------------
# Funções determinísticas (sem rede) — núcleo testável
# ---------------------------------------------------------------------------
def gerar_doc_id(url: str) -> str:
    """Gera o ``doc_id`` estável de um artigo a partir da sua URL.

    **Chave primária do projeto inteiro** (atravessa embedding → tópico → série).
    Derivada apenas da URL: a mesma URL sempre produz o mesmo id, em qualquer
    execução e máquina. Nunca pode ser regenerada a partir de algo mutável.

    Args:
        url: URL canônica do artigo.

    Returns:
        Hash SHA-1 hexadecimal truncado em 16 caracteres.
    """
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def montar_corpus(artigos: list[dict]) -> pd.DataFrame:
    """Monta o DataFrame A1 a partir de uma lista de artigos extraídos (sem rede).

    Gera o ``doc_id``, **deduplica por URL**, **descarta `texto` vazio** e força o
    schema/ordem do contrato A1. Centraliza aqui a lógica determinística para que
    dedup + limpeza + schema sejam testáveis sem acesso à rede.

    Args:
        artigos: dicts com chaves ``url, data, titulo, texto, fonte, categoria``.

    Returns:
        DataFrame no schema A1 (``doc_id, data, titulo, texto, fonte, categoria,
        url``), ``fonte`` como ``category``, sem duplicatas nem textos vazios.
    """
    registros: list[dict] = []
    vistos: set[str] = set()

    for art in artigos:
        url = art["url"]
        if url in vistos:
            continue
        texto = (art.get("texto") or "").strip()
        if not texto:
            continue  # garantia A1: texto não-vazio
        vistos.add(url)
        registros.append(
            {
                "doc_id": gerar_doc_id(url),
                "data": art["data"],
                "titulo": (art.get("titulo") or "").strip(),
                "texto": texto,
                "fonte": art.get("fonte", FONTE),
                "categoria": art.get("categoria"),
                "url": url,
            }
        )

    df = pd.DataFrame(registros, columns=COLUNAS_A1)
    if not df.empty:
        df["fonte"] = df["fonte"].astype("category")
    return df


def filtrar_urls_novas(urls_df: pd.DataFrame, corpus_atual: pd.DataFrame | None) -> pd.DataFrame:
    """Filtra as URLs que ainda NÃO estão no corpus (modo incremental — Story 1.5).

    Permite recoletas diárias baratas: só os artigos novos são baixados e o
    corpus existente é preservado (agregação via :func:`mesclar_corpus`).

    Args:
        urls_df: URLs candidatas (schema da Story 1.2, com coluna ``url``).
        corpus_atual: corpus A1 existente ou ``None``/vazio.

    Returns:
        Subconjunto de ``urls_df`` cujas ``url`` não existem no corpus.
    """
    if corpus_atual is None or corpus_atual.empty:
        return urls_df
    conhecidas = set(corpus_atual["url"])
    return urls_df[~urls_df["url"].isin(conhecidas)].reset_index(drop=True)


def mesclar_corpus(corpus_atual: pd.DataFrame | None, novos: pd.DataFrame) -> pd.DataFrame:
    """Mescla um novo lote (ex.: Canaltech) ao corpus A1, deduplicando por URL.

    Mantém o schema A1 e a primeira ocorrência de cada ``url`` (sem rede). Usado
    para construir o corpus **multi-fonte** da Story 1.4.

    Args:
        corpus_atual: corpus existente (A1) ou ``None``/vazio.
        novos: novo lote no schema A1.

    Returns:
        DataFrame A1 combinado, sem ``url`` duplicada.
    """
    if corpus_atual is None or corpus_atual.empty:
        combinado = novos.copy()
    else:
        combinado = pd.concat([corpus_atual, novos], ignore_index=True)
    combinado = combinado.drop_duplicates(subset="url", keep="first").reset_index(drop=True)
    combinado = combinado.reindex(columns=COLUNAS_A1)
    if not combinado.empty:
        combinado["fonte"] = combinado["fonte"].astype("category")
    return combinado


# ---------------------------------------------------------------------------
# Funções de rede — validadas em amostra (NFR4)
# ---------------------------------------------------------------------------
def extrair_um(url: str, user_agent: str, timeout: int = 30) -> tuple[str, str]:
    """Baixa um artigo e extrai ``(titulo, texto)`` limpos com trafilatura.

    Args:
        url: URL do artigo.
        user_agent: identificação enviada ao servidor (NFR4).
        timeout: tempo máximo da requisição, em segundos.

    Returns:
        Tupla ``(titulo, texto)``; ``texto`` pode ser vazio se a página não tiver
        conteúdo extraível (o chamador trata como "pular").

    Raises:
        requests.RequestException: em falha de rede/HTTP (tratada pelo lote).
    """
    html = baixar(url, user_agent, timeout).decode("utf-8", errors="replace")
    texto = trafilatura.extract(html, include_comments=False) or ""
    titulo = ""
    meta = trafilatura.extract_metadata(html)
    if meta and meta.title:
        titulo = meta.title.strip()
    return titulo, texto.strip()


def carregar_robots(base_url: str, user_agent: str) -> urllib.robotparser.RobotFileParser | None:
    """Carrega e parseia o ``robots.txt`` do host (NFR4 — respeito ao ToS).

    Args:
        base_url: qualquer URL do host (usa-se scheme+host para achar o robots).
        user_agent: identificação para baixar o robots.

    Returns:
        ``RobotFileParser`` pronto para consulta, ou ``None`` se indisponível
        (degradação graciosa: na ausência de robots, assume-se permitido).
    """
    partes = urlsplit(base_url)
    robots_url = urljoin(f"{partes.scheme}://{partes.netloc}", "/robots.txt")
    try:
        conteudo = baixar(robots_url, user_agent).decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001 — robots ausente não deve abortar a coleta
        logger.warning("robots.txt indisponível (%s): %s — assumindo permitido", robots_url, e)
        return None
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(conteudo.splitlines())
    return rp


def extrair_artigos(urls_df: pd.DataFrame, config: Config) -> pd.DataFrame:
    """Extrai o texto de cada URL e monta o corpus A1.

    Respeita rate-limit e ``robots.txt`` (NFR4). Cada extração é protegida por
    try/except: falha → log + pula, **sem abortar o lote** (AC2). Honra o
    ``limite`` opcional da config (amostra/teste).

    Args:
        urls_df: DataFrame da Story 1.2 (``url, data, categoria, fonte``).
        config: configuração validada do projeto.

    Returns:
        DataFrame no schema A1, deduplicado e sem textos vazios.
    """
    params = config.coleta.extract
    # robots.txt cacheado POR HOST: robusto quando o lote mistura fontes
    # (ex.: corpus multi-fonte da Story 1.4). Degradação graciosa: host sem
    # robots acessível → assume permitido.
    robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _permitido(u: str) -> bool:
        host = urlsplit(u).netloc
        if host not in robots_cache:
            robots_cache[host] = carregar_robots(u, params.user_agent)
        rp = robots_cache[host]
        return rp is None or rp.can_fetch(params.user_agent, u)

    artigos: list[dict] = []
    pulados = 0
    for i, row in enumerate(urls_df.itertuples(index=False)):
        if params.limite is not None and i >= params.limite:
            break
        url = row.url
        if not _permitido(url):
            logger.warning("robots.txt bloqueia: %s", url)
            pulados += 1
            continue
        try:
            titulo, texto = extrair_um(url, params.user_agent, params.timeout_s)
            if not texto:
                logger.warning("texto vazio (pulado): %s", url)
                pulados += 1
            else:
                artigos.append(
                    {
                        "url": url,
                        "data": row.data,
                        "titulo": titulo,
                        "texto": texto,
                        "fonte": row.fonte,
                        "categoria": row.categoria,
                    }
                )
        except Exception as e:  # noqa: BLE001 — uma falha não derruba o lote (AC2)
            logger.warning("falha ao extrair %s: %s", url, e)
            pulados += 1
        time.sleep(params.rate_limit_s)

    logger.info("Extração concluída: %d artigos, %d pulados.", len(artigos), pulados)
    return montar_corpus(artigos)


def _config_hash(config_path: str | Path = "config/config.yaml") -> str | None:
    """Hash do arquivo de config (carimbo de reprodutibilidade no manifesto)."""
    p = Path(config_path)
    if not p.exists():
        return None
    return hashlib.sha1(p.read_bytes()).hexdigest()[:16]


def main(argv: list[str] | None = None) -> None:
    """Lê as URLs (1.2), extrai o texto e persiste o corpus A1 + manifesto.

    Modo INCREMENTAL por padrão (Story 1.5): se o corpus já existe, baixa
    apenas as URLs novas e mescla (dedup por url) — recoletas diárias custam
    minutos, não horas, e o corpus só cresce. Use ``--completo`` para
    reconstruir tudo do zero.

    Args:
        argv: argumentos de CLI; ``None`` usa ``sys.argv`` (quem chama via
            código — ex.: run_all — deve passar ``[]`` para não herdar os
            argumentos do processo pai).
    """
    import argparse

    parser = argparse.ArgumentParser(description="Extração de texto → corpus A1 (Story 1.3/1.5)")
    parser.add_argument(
        "--completo", action="store_true",
        help="Re-extrai TODAS as URLs, ignorando o corpus existente (reconstrução total).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config()
    urls_df = ler_parquet(CAMINHO_URLS)

    atual = None
    if not args.completo and CAMINHO_CORPUS.exists():
        atual = ler_parquet(CAMINHO_CORPUS)
        novas = filtrar_urls_novas(urls_df, atual)
        print(f"[i] Modo incremental: {len(novas)} URLs novas de {len(urls_df)} "
              f"(corpus atual: {len(atual)} artigos). Use --completo p/ recoletar tudo.")
        urls_df = novas

    corpus_novos = extrair_artigos(urls_df, config)
    corpus = mesclar_corpus(atual, corpus_novos)
    destino = salvar_parquet(corpus, CAMINHO_CORPUS)

    atualizar_manifest(
        "coleta",
        n_docs=len(corpus),
        stage_version="1.5" if atual is not None else "1.3",
        params={
            "extract.rate_limit_s": config.coleta.extract.rate_limit_s,
            "extract.limite": config.coleta.extract.limite,
            "extract.incremental": atual is not None,
        },
        extras={"config_hash": _config_hash()},
    )

    print(f"[✓] Corpus A1 salvo em {destino} ({len(corpus)} artigos, "
          f"{len(corpus_novos)} novos nesta execução)")
    if not corpus.empty:
        print(f"    Texto vazio: {int((corpus['texto'].str.len() == 0).sum())} (deve ser 0)")
        print(f"    URLs duplicadas: {int(corpus['url'].duplicated().sum())} (deve ser 0)")


if __name__ == "__main__":
    main()
