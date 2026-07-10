"""Testes da extração de texto / dataset A1 (Story 1.3).

Foco determinístico: geração de `doc_id` (estável, derivado só da URL) e a
montagem/dedup/limpeza do DataFrame A1 a partir de artigos simulados. A extração
real (rede) é validada manualmente em amostra (ver Dev Notes da story).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.coleta.extract import (
    COLUNAS_A1,
    filtrar_urls_novas,
    gerar_doc_id,
    mesclar_corpus,
    montar_corpus,
)

URL_A = "https://olhardigital.com.br/2026/06/06/ia/artigo-a/"
URL_B = "https://olhardigital.com.br/2026/06/07/games/artigo-b/"


def _artigo(url: str, *, texto: str = "corpo do artigo", titulo: str = "Titulo",
            data: date = date(2026, 6, 6), categoria: str | None = "ia",
            fonte: str = "olhar_digital") -> dict:
    return {
        "url": url,
        "data": data,
        "titulo": titulo,
        "texto": texto,
        "categoria": categoria,
        "fonte": fonte,
    }


# ---------------------------------------------------------------------------
# gerar_doc_id — chave primária estável (AC3, contrato crítico)
# ---------------------------------------------------------------------------
def test_doc_id_estavel_para_mesma_url() -> None:
    assert gerar_doc_id(URL_A) == gerar_doc_id(URL_A)


def test_doc_id_difere_entre_urls() -> None:
    assert gerar_doc_id(URL_A) != gerar_doc_id(URL_B)


def test_doc_id_tem_16_chars() -> None:
    assert len(gerar_doc_id(URL_A)) == 16


def test_doc_id_depende_so_da_url() -> None:
    """O id NÃO pode mudar se outros campos (data de coleta etc.) mudarem."""
    valor_esperado = gerar_doc_id(URL_A)
    # Mesmo URL em dois artigos com metadados diferentes → mesmo doc_id.
    df = montar_corpus([
        _artigo(URL_A, titulo="T1", data=date(2026, 1, 1)),
        _artigo(URL_B),
    ])
    assert df.loc[df["url"] == URL_A, "doc_id"].iloc[0] == valor_esperado


# ---------------------------------------------------------------------------
# montar_corpus — schema A1, dedup, limpeza (AC3)
# ---------------------------------------------------------------------------
def test_montar_corpus_schema_a1() -> None:
    df = montar_corpus([_artigo(URL_A), _artigo(URL_B)])
    assert list(df.columns) == COLUNAS_A1
    assert len(df) == 2
    assert isinstance(df["fonte"].dtype, pd.CategoricalDtype)


def test_montar_corpus_deduplica_por_url() -> None:
    df = montar_corpus([_artigo(URL_A), _artigo(URL_A), _artigo(URL_B)])
    assert len(df) == 2
    assert df["url"].duplicated().sum() == 0


def test_montar_corpus_descarta_texto_vazio() -> None:
    df = montar_corpus([_artigo(URL_A, texto=""), _artigo(URL_B, texto="   ")])
    assert df.empty
    assert list(df.columns) == COLUNAS_A1


def test_montar_corpus_mantem_categoria_nula() -> None:
    df = montar_corpus([_artigo(URL_A, categoria=None)])
    assert df["categoria"].iloc[0] is None


def test_montar_corpus_texto_e_titulo_sao_strip() -> None:
    df = montar_corpus([_artigo(URL_A, texto="  ola  ", titulo="  T  ")])
    assert df["texto"].iloc[0] == "ola"
    assert df["titulo"].iloc[0] == "T"


def test_montar_corpus_doc_id_bate_com_gerar() -> None:
    df = montar_corpus([_artigo(URL_A)])
    assert df["doc_id"].iloc[0] == gerar_doc_id(URL_A)


def test_montar_corpus_vazio_tem_schema() -> None:
    df = montar_corpus([])
    assert df.empty
    assert list(df.columns) == COLUNAS_A1


# ---------------------------------------------------------------------------
# mesclar_corpus — corpus multi-fonte (Story 1.4, AC2/AC3)
# ---------------------------------------------------------------------------
def test_mesclar_corpus_combina_duas_fontes() -> None:
    olhar = montar_corpus([_artigo(URL_A, fonte="olhar_digital")])
    canaltech = montar_corpus([
        _artigo("https://canaltech.com.br/apps/x/", fonte="canaltech")
    ])
    out = mesclar_corpus(olhar, canaltech)
    assert len(out) == 2
    assert set(out["fonte"].astype(str)) == {"olhar_digital", "canaltech"}
    assert list(out.columns) == COLUNAS_A1


def test_mesclar_corpus_dedup_por_url_entre_fontes() -> None:
    a = montar_corpus([_artigo(URL_A)])
    b = montar_corpus([_artigo(URL_A), _artigo(URL_B)])  # URL_A repetida
    out = mesclar_corpus(a, b)
    assert len(out) == 2
    assert out["url"].duplicated().sum() == 0


def test_mesclar_corpus_base_vazia() -> None:
    novos = montar_corpus([_artigo(URL_A)])
    out = mesclar_corpus(None, novos)
    assert len(out) == 1
    assert list(out.columns) == COLUNAS_A1


# ---------------------------------------------------------------------------
# Modo incremental (Story 1.5)
# ---------------------------------------------------------------------------
def test_filtrar_urls_novas_remove_conhecidas():
    """URLs já presentes no corpus não são re-baixadas."""
    urls = pd.DataFrame({
        "url": ["https://a.com/1", "https://a.com/2", "https://a.com/3"],
        "data": ["2026-07-07"] * 3,
    })
    corpus = pd.DataFrame({"doc_id": ["x1"], "url": ["https://a.com/1"], "texto": ["antigo"]})
    novas = filtrar_urls_novas(urls, corpus)
    assert list(novas["url"]) == ["https://a.com/2", "https://a.com/3"]


def test_filtrar_urls_novas_corpus_vazio_ou_ausente():
    """Sem corpus (primeira coleta), todas as URLs são novas."""
    urls = pd.DataFrame({"url": ["https://a.com/1"], "data": ["2026-07-07"]})
    assert len(filtrar_urls_novas(urls, None)) == 1
    assert len(filtrar_urls_novas(urls, pd.DataFrame(columns=["url"]))) == 1


def test_filtrar_urls_novas_tudo_conhecido():
    """Recoleta sem novidade → zero URLs a baixar (execução barata)."""
    urls = pd.DataFrame({"url": ["https://a.com/1"], "data": ["2026-07-07"]})
    corpus = pd.DataFrame({"url": ["https://a.com/1"], "doc_id": ["x1"]})
    assert len(filtrar_urls_novas(urls, corpus)) == 0


def test_incremental_agrega_sem_perder_dados():
    """Fluxo completo: filtrar novas + mesclar preserva o corpus antigo."""
    atual = montar_corpus([_artigo(URL_A)])
    novos = montar_corpus([_artigo(URL_B, data=date(2026, 7, 7))])
    combinado = mesclar_corpus(atual, novos)
    assert len(combinado) == 2
    assert set(combinado["url"]) == {URL_A, URL_B}
