"""
Grafo de co-ocorrência de termos (Story 4.2).

Constrói um grafo NetworkX onde os nós são termos representativos (c-TF-IDF)
e as arestas ligam termos que co-ocorrem no mesmo tópico. O peso da aresta é
a soma, sobre os tópicos compartilhados, do menor ctfidf_weight do par —
pares fortes em tópicos fortes ganham arestas mais grossas.

Renderização: figura Plotly (scatter de nós + linhas), pronta para
`st.plotly_chart`. O chamador controla o nº de nós exibidos (slider).
"""

from __future__ import annotations

from itertools import combinations

import networkx as nx
import pandas as pd
import plotly.graph_objects as go

# Nº de termos por tópico considerados na co-ocorrência (topo do c-TF-IDF).
TERMOS_POR_TOPICO = 8
# Seed do layout spring (reprodutibilidade visual entre reloads).
LAYOUT_SEED = 42


def construir_grafo(topic_terms: pd.DataFrame, max_nos: int) -> nx.Graph:
    """Monta o grafo de co-ocorrência a partir do topic_terms (contrato A3).

    Args:
        topic_terms: DataFrame {topic_id, term, ctfidf_weight, rank}.
        max_nos: nº máximo de nós no grafo (termos mais fortes primeiro).

    Returns:
        Grafo com nós (atributo `weight` = força total do termo) e arestas
        ponderadas; apenas o maior componente conectado até `max_nos` nós.
    """
    df = topic_terms[topic_terms["topic_id"] != -1].copy()
    df = df[df["rank"] <= TERMOS_POR_TOPICO]

    G = nx.Graph()
    for _, grupo in df.groupby("topic_id"):
        termos = grupo.sort_values("ctfidf_weight", ascending=False)
        pares = list(combinations(termos.itertuples(index=False), 2))
        for a, b in pares:
            peso_par = min(a.ctfidf_weight, b.ctfidf_weight)
            if G.has_edge(a.term, b.term):
                G[a.term][b.term]["weight"] += peso_par
            else:
                G.add_edge(a.term, b.term, weight=peso_par)

    # Força de cada nó = soma dos pesos das arestas (p/ dimensionar e filtrar)
    for no in G.nodes():
        G.nodes[no]["weight"] = sum(d["weight"] for _, _, d in G.edges(no, data=True))

    # Mantém apenas os `max_nos` termos mais fortes (legibilidade — AC2)
    if G.number_of_nodes() > max_nos:
        mais_fortes = sorted(G.nodes(data=True), key=lambda x: -x[1]["weight"])[:max_nos]
        G = G.subgraph([n for n, _ in mais_fortes]).copy()

    return G


def figura_grafo(G: nx.Graph, titulo: str = "Co-ocorrência de termos") -> go.Figure:
    """Converte o grafo NetworkX em figura Plotly (nós + arestas)."""
    if G.number_of_nodes() == 0:
        fig = go.Figure()
        fig.update_layout(title=titulo, annotations=[dict(
            text="Sem termos suficientes para montar o grafo",
            showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
        )])
        return fig

    pos = nx.spring_layout(G, seed=LAYOUT_SEED, weight="weight")

    # Arestas (uma linha por aresta; espessura ~ peso normalizado)
    pesos = [d["weight"] for _, _, d in G.edges(data=True)]
    peso_max = max(pesos) if pesos else 1.0
    edge_traces = []
    for u, v, d in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_traces.append(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines",
            line=dict(width=0.5 + 3.0 * d["weight"] / peso_max, color="#B0BEC5"),
            hoverinfo="none", showlegend=False,
        ))

    # Nós (tamanho ~ força do termo)
    forcas = [G.nodes[n]["weight"] for n in G.nodes()]
    forca_max = max(forcas) if forcas else 1.0
    node_trace = go.Scatter(
        x=[pos[n][0] for n in G.nodes()],
        y=[pos[n][1] for n in G.nodes()],
        mode="markers+text",
        text=list(G.nodes()),
        textposition="top center",
        textfont=dict(size=10),
        marker=dict(
            size=[10 + 25 * f / forca_max for f in forcas],
            color=forcas,
            colorscale="Teal",
            line=dict(width=1, color="#455A64"),
        ),
        hovertext=[f"{n} (força: {G.nodes[n]['weight']:.2f})" for n in G.nodes()],
        hoverinfo="text",
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=titulo,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=40, b=10),
        height=550,
    )
    return fig
