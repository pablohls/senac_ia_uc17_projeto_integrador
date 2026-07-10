"""
Testes da preparação da série temporal do dashboard SONAR
(Story 6.2 — AC8/AC10/AC11/AC12).

Determinísticos, com DataFrames sintéticos e sem I/O. Cobrem: conversão de
`data` para datetime, recorte do período morto (a partir da primeira atividade
menos a margem), tópico sem atividade → vazio, `df` vazio → vazio, presença de
`count_weekly` no resultado e não-mutação/determinismo da função.
"""

import pandas as pd
import pytest
from pandas.api.types import is_datetime64_any_dtype

from src.dashboard.timeseries import preparar_serie


def _serie_sintetica(n_mortos: int = 30, n_ativos: int = 5) -> pd.DataFrame:
    """Série com `data` como string: N dias mortos e depois dias com atividade."""
    total = n_mortos + n_ativos
    datas = pd.date_range("2021-03-18", periods=total, freq="D")
    count_weekly = [0] * n_mortos + list(range(1, n_ativos + 1))
    return pd.DataFrame(
        {
            "topic_id": [139] * total,
            "data": datas.strftime("%Y-%m-%d"),  # string/object, como no parquet real
            "count": [0] * total,
            "count_weekly": count_weekly,
        }
    )


class TestPrepararSerie:
    def test_converte_data_para_datetime(self):
        """AC8: `data` (string) é convertida para datetime64 na saída."""
        out = preparar_serie(_serie_sintetica())
        assert is_datetime64_any_dtype(out["data"])

    def test_mantem_count_weekly(self):
        """AC9: a coluna plotada (`count_weekly`) está presente no resultado."""
        out = preparar_serie(_serie_sintetica())
        assert "count_weekly" in out.columns

    def test_recorta_periodo_morto_com_margem(self):
        """AC10: a primeira linha é `margem_dias` antes da 1ª atividade, não o início da série."""
        margem = 7
        out = preparar_serie(_serie_sintetica(n_mortos=30, n_ativos=5), margem_dias=margem)
        primeira_atividade = pd.Timestamp("2021-03-18") + pd.Timedelta(days=30)
        esperado_inicio = primeira_atividade - pd.Timedelta(days=margem)
        assert out["data"].min() == esperado_inicio
        # não recomeça no início real da série (período morto foi cortado)
        assert out["data"].min() > pd.Timestamp("2021-03-18")

    def test_margem_zero_comeca_na_primeira_atividade(self):
        """AC10/AC12: margem 0 → recorte começa exatamente na 1ª data com atividade."""
        out = preparar_serie(_serie_sintetica(n_mortos=30, n_ativos=5), margem_dias=0)
        assert out["data"].min() == pd.Timestamp("2021-03-18") + pd.Timedelta(days=30)

    def test_topico_sem_atividade_retorna_vazio(self):
        """AC11: count_weekly todo zero → DataFrame vazio, sem exceção."""
        df = _serie_sintetica(n_mortos=20, n_ativos=0)
        out = preparar_serie(df)
        assert out.empty

    def test_df_vazio_retorna_vazio(self):
        """AC11: entrada vazia → saída vazia, sem exceção."""
        vazio = pd.DataFrame(columns=["topic_id", "data", "count", "count_weekly"])
        out = preparar_serie(vazio)
        assert out.empty

    def test_nao_muta_entrada(self):
        """Função pura: o `df` original não é alterado (data continua string)."""
        df = _serie_sintetica()
        preparar_serie(df)
        assert df["data"].dtype == object

    def test_determinismo(self):
        """AC12: mesma entrada → mesma saída em chamadas repetidas."""
        df = _serie_sintetica()
        out1 = preparar_serie(df)
        out2 = preparar_serie(df)
        pd.testing.assert_frame_equal(out1, out2)


@pytest.mark.parametrize("margem", [0, 7, 14])
def test_recorte_nunca_ultrapassa_a_serie(margem):
    """Recorte com margens diferentes nunca inventa datas antes do início da série."""
    out = preparar_serie(_serie_sintetica(n_mortos=5, n_ativos=5), margem_dias=margem)
    assert out["data"].min() >= pd.Timestamp("2021-03-18")
