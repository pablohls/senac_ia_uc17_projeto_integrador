"""
Testes do grafo de co-ocorrência (Story 4.2).
"""

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.graph import construir_grafo, extrair_pontes, figura_grafo


def _topic_terms() -> pd.DataFrame:
    """Dois tópicos compartilhando o termo 'ia' (ponte entre clusters)."""
    linhas = []
    for topic_id, termos in [
        (0, ["ia", "chatgpt", "openai", "modelo"]),
        (1, ["ia", "robô", "automação", "fábrica"]),
        (-1, ["ruído", "outlier"]),  # outliers devem ser ignorados
    ]:
        for rank, termo in enumerate(termos, 1):
            linhas.append({
                "topic_id": topic_id,
                "term": termo,
                "ctfidf_weight": 1.0 / rank,
                "rank": rank,
            })
    return pd.DataFrame(linhas)


class TestGrafoCoocorrencia:
    def test_constroi_nos_e_arestas(self):
        G = construir_grafo(_topic_terms(), max_nos=20)

        # termos dos tópicos válidos viram nós; outliers ficam fora
        assert "ia" in G.nodes()
        assert "ruído" not in G.nodes()

        # termos do mesmo tópico são conectados
        assert G.has_edge("ia", "chatgpt")
        assert G.has_edge("ia", "robô")
        # termos de tópicos diferentes NÃO conectam diretamente
        assert not G.has_edge("chatgpt", "robô")

    def test_termo_compartilhado_acumula_peso(self):
        """'ia' aparece nos 2 tópicos → força maior que termos exclusivos."""
        G = construir_grafo(_topic_terms(), max_nos=20)
        assert G.nodes["ia"]["weight"] > G.nodes["chatgpt"]["weight"]

    def test_limite_de_nos(self):
        """O slider (max_nos) limita o tamanho do grafo (AC2 — legibilidade)."""
        G = construir_grafo(_topic_terms(), max_nos=3)
        assert G.number_of_nodes() <= 3

    def test_figura_plotly(self):
        G = construir_grafo(_topic_terms(), max_nos=20)
        fig = figura_grafo(G)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) > 0

    def test_grafo_vazio_nao_quebra(self):
        vazio = pd.DataFrame({"topic_id": [], "term": [], "ctfidf_weight": [], "rank": []})
        G = construir_grafo(vazio, max_nos=10)
        fig = figura_grafo(G)
        assert isinstance(fig, go.Figure)


def _topic_info() -> pd.DataFrame:
    """Labels dos tópicos do fixture (topic_id → label)."""
    return pd.DataFrame([
        {"topic_id": 0, "label": "IA generativa"},
        {"topic_id": 1, "label": "Automação industrial"},
        {"topic_id": -1, "label": "Outliers"},
    ])


class TestExtrairPontes:
    def test_termo_compartilhado_vira_ponte(self):
        """'ia' está nos tópicos 0 e 1 → aparece como ponte conectando ambos."""
        pontes = extrair_pontes(_topic_terms(), _topic_info())

        assert "ia" in pontes["termo"].values
        linha_ia = pontes[pontes["termo"] == "ia"].iloc[0]
        assert linha_ia["n_topicos"] == 2
        assert linha_ia["peso"] > 0
        # os labels dos dois tópicos conectados aparecem na descrição
        assert "IA generativa" in linha_ia["topicos"]
        assert "Automação industrial" in linha_ia["topicos"]

    def test_termos_exclusivos_nao_sao_pontes(self):
        """Termos de um único tópico (chatgpt, robô) não são pontes."""
        pontes = extrair_pontes(_topic_terms(), _topic_info())
        termos = set(pontes["termo"].values)
        assert "chatgpt" not in termos
        assert "robô" not in termos
        assert "outlier" not in termos  # outliers (topic_id=-1) sempre fora

    def test_sem_pontes_retorna_vazio(self):
        """Tópicos sem termo compartilhado → DataFrame vazio, sem exceção."""
        linhas = []
        for topic_id, termos in [
            (0, ["ia", "chatgpt"]),
            (1, ["robô", "fábrica"]),
        ]:
            for rank, termo in enumerate(termos, 1):
                linhas.append({
                    "topic_id": topic_id,
                    "term": termo,
                    "ctfidf_weight": 1.0 / rank,
                    "rank": rank,
                })
        pontes = extrair_pontes(pd.DataFrame(linhas), _topic_info())
        assert pontes.empty
        assert list(pontes.columns) == ["termo", "topicos", "n_topicos", "peso"]

    def test_entrada_vazia_nao_quebra(self):
        """topic_terms vazio degrada graciosamente (DataFrame vazio)."""
        vazio = pd.DataFrame({"topic_id": [], "term": [], "ctfidf_weight": [], "rank": []})
        pontes = extrair_pontes(vazio, _topic_info())
        assert pontes.empty

    def test_topic_info_ausente_usa_fallback(self):
        """Sem topic_info, os tópicos conectados usam rótulo 'Tópico {id}'."""
        pontes = extrair_pontes(_topic_terms(), None)
        linha_ia = pontes[pontes["termo"] == "ia"].iloc[0]
        assert "Tópico 0" in linha_ia["topicos"]
        assert "Tópico 1" in linha_ia["topicos"]

    def test_top_n_limita_resultado(self):
        """top_n limita o número de pontes retornadas."""
        # três tópicos compartilhando dois termos-ponte distintos
        linhas = []
        for topic_id, termos in [
            (0, ["ia", "dados", "python"]),
            (1, ["ia", "dados", "robô"]),
            (2, ["ia", "nuvem", "api"]),
        ]:
            for rank, termo in enumerate(termos, 1):
                linhas.append({
                    "topic_id": topic_id,
                    "term": termo,
                    "ctfidf_weight": 1.0 / rank,
                    "rank": rank,
                })
        pontes = extrair_pontes(pd.DataFrame(linhas), _topic_info(), top_n=1)
        assert len(pontes) == 1
        # 'ia' conecta 3 tópicos → deve ser a ponte de maior prioridade
        assert pontes.iloc[0]["termo"] == "ia"
