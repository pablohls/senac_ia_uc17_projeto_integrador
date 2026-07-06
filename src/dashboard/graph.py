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
    # + tópico dominante (onde o termo tem maior c-TF-IDF) p/ colorir comunidades
    dominante = df.loc[df.groupby("term")["ctfidf_weight"].idxmax()].set_index("term")["topic_id"]
    for no in G.nodes():
        G.nodes[no]["weight"] = sum(d["weight"] for _, _, d in G.edges(no, data=True))
        G.nodes[no]["topic"] = int(dominante.get(no, -1))

    # Mantém apenas os `max_nos` termos mais fortes (legibilidade — AC2)
    if G.number_of_nodes() > max_nos:
        mais_fortes = sorted(G.nodes(data=True), key=lambda x: -x[1]["weight"])[:max_nos]
        G = G.subgraph([n for n, _ in mais_fortes]).copy()

    return G


# Fração das arestas mais fortes exibidas (as fracas viram poluição visual).
FRACAO_ARESTAS = 0.5
# Fração dos nós mais fortes que recebem rótulo fixo (o resto fica no hover).
FRACAO_ROTULOS = 0.4
# Paleta qualitativa para as comunidades (tópico dominante do termo).
PALETA = [
    "#0b7285", "#c05621", "#5f3dc4", "#2b8a3e", "#c2255c",
    "#e67700", "#1864ab", "#087f5b", "#862e9c", "#a61e4d",
]


def figura_grafo(G: nx.Graph, titulo: str = "Co-ocorrência de termos") -> go.Figure:
    """Converte o grafo NetworkX em figura Plotly legível.

    Legibilidade (AC2 da Story 4.2): cor = comunidade (tópico dominante do
    termo); rótulo fixo apenas nos termos mais fortes (demais no hover);
    somente as arestas mais fortes são desenhadas; layout espalhado.
    """
    if G.number_of_nodes() == 0:
        fig = go.Figure()
        fig.update_layout(title=titulo, annotations=[dict(
            text="Sem termos suficientes para montar o grafo",
            showarrow=False, xref="paper", yref="paper", x=0.5, y=0.5,
        )])
        return fig

    n = G.number_of_nodes()
    # k maior espalha os nós; iterações extras estabilizam o layout
    pos = nx.spring_layout(G, seed=LAYOUT_SEED, weight="weight",
                           k=1.8 / max(n, 1) ** 0.5, iterations=100)

    # Arestas: desenha só a fração mais forte (reduz o "novelo de lã")
    arestas = sorted(G.edges(data=True), key=lambda e: -e[2]["weight"])
    visiveis = arestas[:max(1, int(len(arestas) * FRACAO_ARESTAS))]
    peso_max = visiveis[0][2]["weight"] if visiveis else 1.0
    edge_traces = []
    for u, v, d in visiveis:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_traces.append(go.Scatter(
            x=[x0, x1], y=[y0, y1], mode="lines",
            line=dict(width=0.6 + 2.4 * d["weight"] / peso_max, color="#B0BEC5"),
            opacity=0.45, hoverinfo="none", showlegend=False,
        ))

    # Nós: tamanho ~ força; cor = comunidade; rótulo fixo só nos mais fortes
    nos = list(G.nodes())
    forcas = [G.nodes[n_]["weight"] for n_ in nos]
    forca_max = max(forcas) if forcas else 1.0
    corte_rotulo = sorted(forcas, reverse=True)[max(0, int(len(nos) * FRACAO_ROTULOS) - 1)]
    topicos = sorted({G.nodes[n_]["topic"] for n_ in nos})
    cor_do_topico = {t: PALETA[i % len(PALETA)] for i, t in enumerate(topicos)}

    node_trace = go.Scatter(
        x=[pos[n_][0] for n_ in nos],
        y=[pos[n_][1] for n_ in nos],
        mode="markers+text",
        text=[n_ if G.nodes[n_]["weight"] >= corte_rotulo else "" for n_ in nos],
        textposition="top center",
        textfont=dict(size=11),
        marker=dict(
            size=[12 + 26 * f / forca_max for f in forcas],
            color=[cor_do_topico[G.nodes[n_]["topic"]] for n_ in nos],
            opacity=0.9,
            line=dict(width=1, color="white"),
        ),
        hovertext=[
            f"<b>{n_}</b><br>força: {G.nodes[n_]['weight']:.2f}<br>comunidade: tópico {G.nodes[n_]['topic']}"
            for n_ in nos
        ],
        hoverinfo="text",
        showlegend=False,
    )

    fig = go.Figure(data=edge_traces + [node_trace])
    fig.update_layout(
        title=titulo,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=10, r=10, t=40, b=10),
        height=620,
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig
