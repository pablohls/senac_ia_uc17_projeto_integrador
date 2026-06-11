"""Testes da extração de texto / dataset A1 (Story 1.3).

Foco determinístico: geração de `doc_id` (estável, derivado só da URL) e a
montagem/dedup/limpeza do DataFrame A1 a partir de artigos simulados. A extração
real (rede) é validada manualmente em amostra (ver Dev Notes da story).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.coleta.extract import COLUNAS_A1, gerar_doc_id, montar_corpus

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
