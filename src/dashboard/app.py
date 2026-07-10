"""
Dashboard SONAR — Sistema de Observação de Narrativas e Assuntos Relevantes
(Fase 4 — Stories 4.1, 4.2, 4.3; Fase 5 — Story 5.3; rebrand/tema/série — Story 6.2).

Precompute-then-serve: lê somente artefatos gerados offline pelas Fases 2-3/5
(contratos A3/A4/A5) — nenhum cálculo pesado acontece aqui (NFR8, carga < 5s).

Uso: poetry run streamlit run src/dashboard/app.py
"""

import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from src.common.llm import llm_disponivel
from src.dashboard.graph import PALETA, construir_grafo, extrair_pontes, figura_grafo
from src.dashboard.insight import aplicar_insight, carregar_briefings
from src.dashboard.timeseries import preparar_serie
from src.rag.responder import MSG_INDISPONIVEL, responder_stream

# Configuração da página para otimizar o layout
st.set_page_config(
    page_title="SONAR - Dashboard",
    page_icon="📡",
    layout="wide"
)

# CSS pontual (Story 6.1): apenas espaçamento entre seções/headers — sem
# componentes funcionais em HTML. Único bloco de style do dashboard.
st.markdown(
    """
    <style>
    .block-container { padding-top: 3rem; }
    h2 { margin-top: 0.6rem; }
    hr { margin: 1.4rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
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

    # Briefings do Analista IA (A5) são OPCIONAIS (Story 5.3 — mesmo padrão)
    artifacts["briefings"] = carregar_briefings()

    return artifacts

# -----------------------------------------------------------------------------
# Inicialização e Tratamento de Erros
# -----------------------------------------------------------------------------
st.title("📡 SONAR: Sistema de Observação de Narrativas e Assuntos Relevantes")
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

# Analista IA (Story 5.3): com A5 presente, label_llm substitui o c-TF-IDF;
# sem A5, df_ranking volta intacto e o dashboard fica como antes da Fase 5.
df_ranking, tem_insight = aplicar_insight(df_ranking, artifacts["briefings"])
if tem_insight:
    modelo_insight = artifacts["briefings"]["model_name"].iloc[0]
    st.caption(
        f"🧠 Analista IA ativo — rótulos e análises gerados por LLM local ({modelo_insight})."
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
# Story 6.1: Cards de métricas (visão geral do corpus no topo do dashboard)
# -----------------------------------------------------------------------------
n_docs = df_corpus_meta["doc_id"].nunique()
n_topicos_validos = len(df_ranking)
_datas = pd.to_datetime(df_doc_topics["data"], errors="coerce").dropna()
periodo = f"{_datas.min():%d/%m/%Y} – {_datas.max():%d/%m/%Y}" if not _datas.empty else "—"
top_trend = str(df_ranking.iloc[0]["label"]) if not df_ranking.empty else "—"

card1, card2, card3, card4 = st.columns(4)
card1.metric("📄 Documentos", f"{n_docs:,}".replace(",", "."))
card2.metric("🗂️ Tópicos válidos", n_topicos_validos)
card3.metric("📅 Período coberto", periodo)
card4.metric("🚀 Top trend", top_trend)

st.divider()

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
st.markdown(
    "Selecione um tópico para aprofundar na sua evolução, palavras-chave e artigos originais."
)

# Selectbox usando o Label, mas guardando o ID do tópico para os filtros
opcoes_topicos = df_ranking.set_index("topic_id")["label"].to_dict()
topico_selecionado_id = st.selectbox(
    "Escolha o Tópico:",
    options=list(opcoes_topicos.keys()),
    format_func=lambda x: opcoes_topicos[x]
)

if topico_selecionado_id is not None:
    # Aba "🧠 Análise" só existe quando o Analista IA está disponível (Story 5.3)
    nomes_abas = ["📈 Série Temporal", "🔠 Termos Representativos", "📰 Artigos-Fonte"]
    if tem_insight:
        nomes_abas.insert(0, "🧠 Análise")
        tab_analise, tab1, tab2, tab3 = st.tabs(nomes_abas)
    else:
        tab1, tab2, tab3 = st.tabs(nomes_abas)

    # Filtra os dados apenas para o tópico selecionado
    topic_serie = df_series[df_series["topic_id"] == topico_selecionado_id]
    topic_terms = df_topic_terms[df_topic_terms["topic_id"] == topico_selecionado_id]
    topic_articles = df_artigos[df_artigos["topic_id"] == topico_selecionado_id]

    # Aba 0 (Story 5.3): "por que sobe" gerado pelo Analista IA (batch, A5)
    if tem_insight:
        with tab_analise:
            linha_topico = df_ranking[df_ranking["topic_id"] == topico_selecionado_id]
            why = ""
            if not linha_topico.empty:
                why = str(linha_topico.iloc[0].get("why_summary") or "").strip()
            if why:
                st.markdown(f"**Por que este tópico está subindo?**\n\n{why}")
                st.caption(
                    f"Análise gerada por LLM local ({modelo_insight}) — Analista IA (batch)."
                )
            else:
                st.info("Sem análise do Analista IA para este tópico (fallback c-TF-IDF).")

    # Aba 1: Gráfico Temporal — schema real: {topic_id, data, count, count_weekly}
    # Story 6.2: converte `data` p/ datetime, plota `count_weekly` (o sinal real
    # está na contagem semanal) e recorta o período morto inicial (função pura).
    with tab1:
        serie_plot = preparar_serie(topic_serie)
        if not serie_plot.empty:
            fig = px.line(
                serie_plot,
                x="data",
                y="count_weekly",
                title=f"Evolução no Tempo: {opcoes_topicos[topico_selecionado_id]}",
                markers=True,
                labels={"data": "Data", "count_weekly": "Artigos por semana"},
                color_discrete_sequence=PALETA,
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
# Story 6.1: Pontes entre tópicos (reenquadra o Grafo de Co-ocorrência da 4.2)
# -----------------------------------------------------------------------------
st.header("🔗 Pontes entre tópicos")
st.markdown(
    "Uma **ponte** é um termo que aparece entre as palavras-chave de mais de um "
    "tópico — sinaliza uma **pauta emergente na interseção de temas**. Quanto mais "
    "tópicos um termo conecta (e quanto mais forte sua co-ocorrência), mais central "
    "ele é para entender onde os assuntos se cruzam."
)

df_pontes = extrair_pontes(df_topic_terms, df_topic_info)
if df_pontes.empty:
    st.info(
        "Nenhum termo-ponte no período — os termos representativos estão "
        "concentrados em tópicos distintos, sem interseção relevante entre eles."
    )
else:
    st.dataframe(
        df_pontes.rename(columns={
            "termo": "Termo",
            "topicos": "Tópicos conectados",
            "n_topicos": "Nº de tópicos",
            "peso": "Força",
        }).style.format({"Força": "{:.2f}"}),
        width='stretch',
        hide_index=True,
    )


@st.cache_data
def _grafo_cacheado(topic_terms: pd.DataFrame, max_nos: int):
    """Monta o grafo cacheado por (dados, nº de nós)."""
    G = construir_grafo(topic_terms, max_nos=max_nos)
    return figura_grafo(G)


# Story 4.2 preservada: o grafo completo continua disponível, só recolhido.
with st.expander("Visão avançada: grafo completo"):
    st.markdown(
        "Termos que aparecem juntos nos mesmos tópicos. **Cor** = comunidade "
        "(tópico dominante); **tamanho** = força do termo; **espessura da aresta** = "
        "força da co-ocorrência. Passe o mouse sobre um nó para ver o nome e a "
        "comunidade — só os termos mais fortes têm rótulo fixo."
    )
    max_nos = st.slider("Número de termos no grafo:", min_value=10, max_value=80, value=30, step=5)
    st.plotly_chart(
        _grafo_cacheado(df_topic_terms, max_nos),
        width='stretch',
    )

st.divider()

# -----------------------------------------------------------------------------
# Story 5.5: Chat RAG — converse com as tendências (guardado por tem_rag)
# -----------------------------------------------------------------------------
tem_rag = llm_disponivel()

if tem_rag:
    st.header("💬 Converse com as Tendências")
    st.markdown(
        "Pergunte em linguagem natural sobre as notícias coletadas. As respostas "
        "são geradas por LLM local e **citam os artigos-fonte** — verifique cada "
        "afirmação na matéria original."
    )

    if "chat_historico" not in st.session_state:
        st.session_state.chat_historico = []

    for msg in st.session_state.chat_historico:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    pergunta = st.chat_input("Ex.: o que está acontecendo com os preços do iPhone?")
    if pergunta:
        st.session_state.chat_historico.append({"role": "user", "content": pergunta})
        with st.chat_message("user"):
            st.markdown(pergunta)

        with st.chat_message("assistant"):
            resultado = responder_stream(pergunta)
            if resultado["tokens"] is None:
                # Sem base no corpus: recusa honesta, sem chamar o LLM (AC3/AC5)
                texto = resultado["resposta_pronta"]
                st.markdown(texto)
            else:
                # Streaming token a token (AC4); stream vazio = LLM caiu (AC5)
                texto = st.write_stream(resultado["tokens"]) or ""
                if not texto.strip():
                    texto = MSG_INDISPONIVEL
                    st.markdown(texto)

            if resultado["citacoes"] and texto not in (MSG_INDISPONIVEL,):
                fontes_md = "\n".join(
                    f"- [{c['titulo']}]({c['url']}) `{c['fonte']}`"
                    for c in resultado["citacoes"]
                )
                st.markdown(f"**Fontes:**\n{fontes_md}")
                texto = f"{texto}\n\n**Fontes:**\n{fontes_md}"

        st.session_state.chat_historico.append({"role": "assistant", "content": texto})
else:
    st.caption(
        "💬 Chat com as tendências indisponível (endpoint LLM fora do ar) — "
        "o restante do dashboard segue normal."
    )
