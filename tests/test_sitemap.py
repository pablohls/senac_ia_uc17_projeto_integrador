"""Testes do coletor de sitemap (Story 1.2).

Foco: a lógica **determinística** (sem rede) — derivação de data/categoria a
partir da URL, seleção de meses, dedup, filtro e schema de saída. A parte de
rede é validada manualmente (ver Dev Notes da story).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.coleta.sitemap import (
    FONTE,
    FONTE_CANALTECH,
    construir_dataframe,
    construir_urls_canaltech,
    data_corte,
    meses_alvo,
    parse_artigo,
    parse_categoria_canaltech,
    urls_de_xml,
)

# URLs de exemplo fixas (fixtures), no padrão real do Olhar Digital.
URL_VALIDA = "https://olhardigital.com.br/2026/06/06/ciencia-e-espaco/novo-telescopio/"
URL_VALIDA_2 = "https://olhardigital.com.br/2026/05/20/seguranca/golpe-pix/"
URL_OUTRA_CAT = "https://olhardigital.com.br/2026/06/01/games/lancamento-jogo/"
URL_INSTITUCIONAL = "https://olhardigital.com.br/sobre/"
URL_DATA_INVALIDA = "https://olhardigital.com.br/2026/13/40/games/data-impossivel/"


# ---------------------------------------------------------------------------
# parse_artigo — a função determinística central (AC2)
# ---------------------------------------------------------------------------
def test_parse_artigo_extrai_data_e_categoria() -> None:
    resultado = parse_artigo(URL_VALIDA)
    assert resultado == (date(2026, 6, 6), "ciencia-e-espaco")


def test_parse_artigo_sem_barra_final() -> None:
    """URLs com e sem barra final devem casar igualmente."""
    assert parse_artigo(URL_VALIDA.rstrip("/")) == (date(2026, 6, 6), "ciencia-e-espaco")


def test_parse_artigo_ignora_url_institucional() -> None:
    assert parse_artigo(URL_INSTITUCIONAL) is None


def test_parse_artigo_descarta_data_impossivel() -> None:
    assert parse_artigo(URL_DATA_INVALIDA) is None


# ---------------------------------------------------------------------------
# meses_alvo — seleção da janela histórica (AC1)
# ---------------------------------------------------------------------------
def test_meses_alvo_volta_no_tempo_incluindo_corrente() -> None:
    rotulos = meses_alvo(4, hoje=date(2026, 3, 15))
    assert rotulos == ["2026-03", "2026-02", "2026-01", "2025-12"]


def test_meses_alvo_um_mes() -> None:
    assert meses_alvo(1, hoje=date(2026, 6, 11)) == ["2026-06"]


# ---------------------------------------------------------------------------
# construir_dataframe — dedup, filtro e schema (AC2, AC3)
# ---------------------------------------------------------------------------
def test_construir_dataframe_schema_e_conteudo() -> None:
    df = construir_dataframe([URL_VALIDA, URL_VALIDA_2])
    assert list(df.columns) == ["url", "data", "categoria", "fonte"]
    assert len(df) == 2
    assert df["fonte"].iloc[0] == FONTE
    assert isinstance(df["data"].iloc[0], date)


def test_construir_dataframe_deduplica_por_url() -> None:
    df = construir_dataframe([URL_VALIDA, URL_VALIDA, URL_VALIDA_2])
    assert len(df) == 2
    assert df["url"].duplicated().sum() == 0


def test_construir_dataframe_descarta_nao_artigos() -> None:
    df = construir_dataframe([URL_VALIDA, URL_INSTITUCIONAL, URL_DATA_INVALIDA])
    assert len(df) == 1
    assert df["url"].iloc[0] == URL_VALIDA


def test_construir_dataframe_filtra_por_categoria() -> None:
    df = construir_dataframe(
        [URL_VALIDA, URL_VALIDA_2, URL_OUTRA_CAT], categorias=["games"]
    )
    assert len(df) == 1
    assert df["categoria"].iloc[0] == "games"


def test_construir_dataframe_vazio_tem_schema() -> None:
    """Lista sem artigos válidos retorna DataFrame vazio mas com as colunas certas."""
    df = construir_dataframe([URL_INSTITUCIONAL])
    assert df.empty
    assert list(df.columns) == ["url", "data", "categoria", "fonte"]


def test_construir_dataframe_fonte_e_category() -> None:
    df = construir_dataframe([URL_VALIDA])
    assert isinstance(df["fonte"].dtype, pd.CategoricalDtype)


# ---------------------------------------------------------------------------
# urls_de_xml — parse de XML de sitemap (sem rede, bytes fixos)
# ---------------------------------------------------------------------------
def test_urls_de_xml_extrai_locs() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://olhardigital.com.br/2026/06/06/ia/artigo-a/</loc></url>
      <url><loc>https://olhardigital.com.br/2026/06/07/ia/artigo-b/</loc></url>
    </urlset>"""
    locs = urls_de_xml(xml)
    assert locs == [
        "https://olhardigital.com.br/2026/06/06/ia/artigo-a/",
        "https://olhardigital.com.br/2026/06/07/ia/artigo-b/",
    ]


# ---------------------------------------------------------------------------
# Canaltech (Story 1.4) — data vem do <lastmod>, categoria do path
# ---------------------------------------------------------------------------
CT_ARTIGO = "https://canaltech.com.br/apps/whatsapp-vai-exigir-atualizacao/"
CT_SECAO = "https://canaltech.com.br/apps/"  # página de seção (não é artigo)


def test_parse_categoria_canaltech_extrai_primeiro_segmento() -> None:
    assert parse_categoria_canaltech(CT_ARTIGO) == "apps"


def test_parse_categoria_canaltech_ignora_pagina_de_secao() -> None:
    assert parse_categoria_canaltech(CT_SECAO) is None


def test_data_corte_primeiro_dia_do_mes_mais_antigo() -> None:
    assert data_corte(4, hoje=date(2026, 6, 11)) == date(2026, 3, 1)


def test_data_corte_um_mes() -> None:
    assert data_corte(1, hoje=date(2026, 6, 11)) == date(2026, 6, 1)


def test_data_corte_vira_o_ano() -> None:
    assert data_corte(4, hoje=date(2026, 2, 10)) == date(2025, 11, 1)


def test_construir_urls_canaltech_filtra_janela_e_deriva_data() -> None:
    registros = [
        (CT_ARTIGO, "2026-05-20T10:00:00-03:00"),                 # dentro da janela
        ("https://canaltech.com.br/games/jogo-antigo/", "2024-01-02T08:00:00-03:00"),  # fora
    ]
    df = construir_urls_canaltech(registros, corte=date(2026, 3, 1))
    assert list(df.columns) == ["url", "data", "categoria", "fonte"]
    assert len(df) == 1
    assert df["data"].iloc[0] == date(2026, 5, 20)
    assert df["categoria"].iloc[0] == "apps"
    assert df["fonte"].iloc[0] == FONTE_CANALTECH


def test_construir_urls_canaltech_dedup_e_ignora_secao() -> None:
    registros = [
        (CT_ARTIGO, "2026-05-20T10:00:00-03:00"),
        (CT_ARTIGO, "2026-05-21T10:00:00-03:00"),  # url repetida
        (CT_SECAO, "2026-05-20T10:00:00-03:00"),   # seção → descartada
    ]
    df = construir_urls_canaltech(registros, corte=date(2026, 3, 1))
    assert len(df) == 1
    assert df["url"].duplicated().sum() == 0


def test_construir_urls_canaltech_lastmod_invalido_descartado() -> None:
    df = construir_urls_canaltech([(CT_ARTIGO, "")], corte=date(2026, 3, 1))
    assert df.empty
    assert list(df.columns) == ["url", "data", "categoria", "fonte"]
