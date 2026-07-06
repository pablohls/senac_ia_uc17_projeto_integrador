"""
Dashboard TrendRadar (Fase 4 — Stories 4.1, 4.2, 4.3).

Precompute-then-serve: lê somente artefatos gerados offline pelas Fases 2-3
(contratos A3/A4) — nenhum cálculo pesado acontece aqui (NFR8, carga < 5s).

Uso: poetry run streamlit run src/dashboard/app.py
"""

import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.graph import construir_grafo, figura_grafo

# Configuração da página para otimizar o layout
st.set_page_config(
    page_title="TrendRadar - Dashboard",
    page_icon="📈",
    layout="wide"
)

# -----------------------------------------------------------------------------
# Task 1: Carregar artefatos (cacheado)
# -----------------------------------------------------------------------------
@st.cache_data
def load_artifacts():
    """
    Lê os artefatos pré-computados offline de forma otimizada.
    Garante o carregamento da tela em < 5s (NFR8).
    Retorna os dataframes ou None se algum arquivo essencial faltar.

    Contratos (schemas reais das Fases 2-3):
      scores.parquet      {topic_id, trend_score, growth, is_new, support_ok, ...
                           [pred_lstm, surprise_z, is_anomaly — Camada 2]}
      series.parquet      {topic_id, data, count, count_weekly}
      topic_info.parquet  {topic_id, label, size, first_seen_date, last_seen_date}
      topic_terms.parquet {topic_id, term, ctfidf_weight, rank}
      doc_topics.parquet  {doc_id, data, topic_id[, probabilidade]}
      corpus.parquet      {doc_id, titulo, url, fonte, ...} (A1 congelado; só metadados lidos)
    """
    base_path = "dados"

    files = {
        "scores": os.path.join(base_path, "scores", "scores.parquet"),
        "series": os.path.join(base_path, "scores", "series.parquet"),
        "topic_info": os.path.join(base_path, "topics", "topic_info.parquet"),
        "topic_terms": os.path.join(base_path, "topics", "topic_terms.parquet"),
        "doc_topics": os.path.join(base_path, "topics", "doc_topics.parquet"),
        # Metadados dos artigos vêm do corpus A1 (versionado) — o dashboard
        # funciona logo após o clone, sem precisar rodar o pipeline.
        "corpus": os.path.join(base_path, "raw", "corpus.parquet"),
    }

    # Verifica se os arquivos existem antes de ler
    for name, path in files.items():
        if not os.path.exists(path):
            return None

    artifacts = {
        "scores": pd.read_parquet(files["scores"]),
        "series": pd.read_parquet(files["series"]),
        "topic_info": pd.read_parquet(files["topic_info"]),
        "topic_terms": pd.read_parquet(files["topic_terms"]),
        # Do corpus só os metadados dos artigos (leve — não carrega os textos)
        "corpus_meta": pd.read_parquet(
            files["corpus"], columns=["doc_id", "titulo", "url", "fonte"]
        ),
        "doc_topics": pd.read_parquet(files["doc_topics"]),
    }

    # Alertas da Camada 2 são OPCIONAIS (Story 4.3 — degradação graciosa)
    alerts_path = os.path.join(base_path, "scores", "alerts.json")
    if os.path.exists(alerts_path):
        with open(alerts_path, encoding="utf-8") as f:
            artifacts["alerts"] = json.load(f)
    else:
        artifacts["alerts"] = None

    return artifacts

# -----------------------------------------------------------------------------
# Inicialização e Tratamento de Erros
# -----------------------------------------------------------------------------
st.title("📈 TrendRadar: Tópicos em Ascensão")
st.markdown("Acompanhe as tendências do setor identificadas pelo nosso pipeline.")

artifacts = load_artifacts()

if artifacts is None:
    st.warning(
        "⚠️ Artefatos não encontrados. Rode o pipeline primeiro: "
        "`poetry run python -m src.pln.run` (Fase 2) e "
        "`poetry run python -m src.scores.run` (Fase 3)."
    )
    st.stop()

# Desempacotando os dataframes
df_scores = artifacts["scores"]
df_series = artifacts["series"]
df_topic_info = artifacts["topic_info"]
df_topic_terms = artifacts["topic_terms"]
df_corpus_meta = artifacts["corpus_meta"]
df_doc_topics = artifacts["doc_topics"]
alerts = artifacts["alerts"]

# Vínculo artigo ↔ tópico (o corpus não tem topic_id; o join é via doc_topics)
df_artigos = df_doc_topics.merge(df_corpus_meta, on="doc_id", how="left")

# Mesclando scores com informações do tópico para ter os labels na mesma tabela.
# Outliers (topic_id = -1) e tópicos sem suporte mínimo ficam fora do ranking.
df_ranking = df_scores.merge(df_topic_info[["topic_id", "label"]], on="topic_id", how="left")
df_ranking = df_ranking[(df_ranking["topic_id"] != -1) & (df_ranking["support_ok"])]
df_ranking = df_ranking.sort_values(by="trend_score", ascending=False).reset_index(drop=True)

# Disponibilidade da Camada 2 (Story 4.3): coluna presente e com algum valor
tem_camada2 = (
    "surprise_z" in df_ranking.columns and df_ranking["surprise_z"].notna().any()
)

# -----------------------------------------------------------------------------
# Story 4.3: Alertas visuais de anomalia (com degradação graciosa)
# -----------------------------------------------------------------------------
if tem_camada2:
    if alerts:
        ids_alerta = {a["topic_id"] for a in alerts}
        labels_alerta = df_ranking[df_ranking["topic_id"].isin(ids_alerta)]["label"].tolist()
        st.error(
            f"🚨 **{len(alerts)} anomalia(s) detectada(s)** pela Camada 2 (LSTM): "
            + "; ".join(f"**{lb}**" for lb in labels_alerta)
        )
    else:
        st.caption("✅ Camada 2 (LSTM) ativa — nenhuma anomalia no período.")
else:
    st.caption("ℹ️ Camada 2 (LSTM) indisponível — exibindo apenas o score estatístico (Camada 1).")

# -----------------------------------------------------------------------------
# Task 2: Painel Principal (Lista Ranqueada)
# -----------------------------------------------------------------------------
st.header("🔥 Em Alta")


def _badges(row) -> str:
    """Badges do tópico: 🆕 (novo) e 🚨 (anomalia da Camada 2)."""
    partes = []
    if row.get("is_new"):
        partes.append("🆕")
    if tem_camada2 and bool(row.get("is_anomaly")):
        partes.append("🚨")
    return " ".join(partes)


# Exibição do ranking em formato de métricas (Cards) para os Top 3
top_cols = st.columns(3)
for i in range(min(3, len(df_ranking))):
    with top_cols[i]:
        row = df_ranking.iloc[i]
        st.metric(
            label=f"{_badges(row)} {row['label']}".strip(),
            value=f"Score: {row['trend_score']:.2f}",
            delta=f"{row['growth']:.2%} Crescimento"
        )

st.markdown("### Tabela Completa de Ascensão")
df_tabela = df_ranking.copy()
df_tabela["status"] = df_tabela.apply(_badges, axis=1)
colunas_tabela = ["status", "topic_id", "label", "trend_score", "growth"]
if tem_camada2:
    colunas_tabela.append("surprise_z")

st.dataframe(
    df_tabela[colunas_tabela].style.format({
        "trend_score": "{:.2f}",
        "growth": "{:.2%}",
        **({"surprise_z": "{:.2f}"} if tem_camada2 else {}),
    }),
    width='stretch',
    hide_index=True
)

st.divider()

# -----------------------------------------------------------------------------
# Task 3: Drill-down do Tópico
# -----------------------------------------------------------------------------
st.header("🔎 Drill-down de Tópicos")
st.markdown("Selecione um tópico para aprofundar na sua evolução, palavras-chave e artigos originais.")

# Selectbox usando o Label, mas guardando o ID do tópico para os filtros
opcoes_topicos = df_ranking.set_index("topic_id")["label"].to_dict()
topico_selecionado_id = st.selectbox(
    "Escolha o Tópico:",
    options=list(opcoes_topicos.keys()),
    format_func=lambda x: opcoes_topicos[x]
)

if topico_selecionado_id is not None:
    tab1, tab2, tab3 = st.tabs(["📈 Série Temporal", "🔠 Termos Representativos", "📰 Artigos-Fonte"])

    # Filtra os dados apenas para o tópico selecionado
    topic_serie = df_series[df_series["topic_id"] == topico_selecionado_id]
    topic_terms = df_topic_terms[df_topic_terms["topic_id"] == topico_selecionado_id]
    topic_articles = df_artigos[df_artigos["topic_id"] == topico_selecionado_id]

    # Aba 1: Gráfico Temporal — schema real: {topic_id, data, count}
    with tab1:
        if not topic_serie.empty:
            fig = px.line(
                topic_serie,
                x="data",
                y="count",
                title=f"Evolução no Tempo: {opcoes_topicos[topico_selecionado_id]}",
                markers=True,
                labels={"data": "Data", "count": "Artigos por dia"},
            )
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("Sem dados temporais para exibir.")

    # Aba 2: Termos Representativos — schema real: {term, ctfidf_weight, rank}
    with tab2:
        if not topic_terms.empty:
            st.markdown("Termos mais relevantes que compõem este assunto (c-TF-IDF):")
            st.dataframe(
                topic_terms[["term", "ctfidf_weight"]]
                .sort_values(by="ctfidf_weight", ascending=False)
                .rename(columns={"term": "Termo", "ctfidf_weight": "Peso (c-TF-IDF)"}),
                width='stretch',
                hide_index=True
            )
        else:
            st.info("Termos não disponíveis.")

    # Aba 3: Artigos Fonte — schema real: {titulo, url} via join doc_topics×corpus
    with tab3:
        if not topic_articles.empty:
            st.markdown(f"**{len(topic_articles)} artigos** relacionados encontrados:")
            for _, artigo in topic_articles.head(50).iterrows():
                titulo = artigo.get("titulo") or "Sem título"
                link = artigo.get("url") or "#"
                fonte = artigo.get("fonte") or ""
                st.markdown(f"- [{titulo}]({link}) `{fonte}`")
            if len(topic_articles) > 50:
                st.caption(f"Exibindo 50 de {len(topic_articles)} artigos.")
        else:
            st.info("Nenhum artigo encontrado para este tópico.")

st.divider()

# -----------------------------------------------------------------------------
# Story 4.2: Grafo de Co-ocorrência de Termos
# -----------------------------------------------------------------------------
st.header("🕸️ Grafo de Co-ocorrência")
st.markdown(
    "Termos que aparecem juntos nos mesmos tópicos. O tamanho do nó indica a "
    "força do termo; a espessura da aresta, a força da co-ocorrência."
)

max_nos = st.slider("Número de termos no grafo:", min_value=10, max_value=80, value=30, step=5)


@st.cache_data
def _grafo_cacheado(topic_terms: pd.DataFrame, max_nos: int):
    """Monta o grafo cacheado por (dados, nº de nós)."""
    G = construir_grafo(topic_terms, max_nos=max_nos)
    return figura_grafo(G)


st.plotly_chart(
    _grafo_cacheado(df_topic_terms, max_nos),
    width='stretch',
)
