"""
Testes do grafo de co-ocorrência (Story 4.2).
"""

import pandas as pd
import plotly.graph_objects as go

from src.dashboard.graph import construir_grafo, figura_grafo


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
