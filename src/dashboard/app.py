import streamlit as st
import pandas as pd
import plotly.express as px
import os

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
    """
    base_path = "dados" # Caminho base esperado conforme guia
    
    # Dicionário mapeando os arquivos necessários
    files = {
        "scores": os.path.join(base_path, "scores", "scores.parquet"),
        "series": os.path.join(base_path, "scores", "series.parquet"),
        "topic_info": os.path.join(base_path, "topics", "topic_info.parquet"),
        "topic_terms": os.path.join(base_path, "topics", "topic_terms.parquet"),
        "corpus": os.path.join(base_path, "topics", "corpus.parquet")
    }
    
    # Verifica se os arquivos existem antes de ler
    for name, path in files.items():
        if not os.path.exists(path):
            return None
    
    # Carregamento otimizado (read-only)
    artifacts = {
        "scores": pd.read_parquet(files["scores"]),
        "series": pd.read_parquet(files["series"]),
        "topic_info": pd.read_parquet(files["topic_info"]),
        "topic_terms": pd.read_parquet(files["topic_terms"]),
        "corpus": pd.read_parquet(files["corpus"])
    }
    
    return artifacts

# -----------------------------------------------------------------------------
# Inicialização e Tratamento de Erros
# -----------------------------------------------------------------------------
st.title("📈 TrendRadar: Tópicos em Ascensão")
st.markdown("Acompanhe as tendências do setor identificadas pelo nosso pipeline.")

artifacts = load_artifacts()

if artifacts is None:
    st.warning("⚠️ Artefatos não encontrados. Por favor, rode o pipeline de extração e modelagem primeiro para gerar os arquivos parquet na pasta `dados/`.")
    st.stop()

# Desempacotando os dataframes
df_scores = artifacts["scores"]
df_series = artifacts["series"]
df_topic_info = artifacts["topic_info"]
df_topic_terms = artifacts["topic_terms"]
df_corpus = artifacts["corpus"]

# Mesclando scores com informações do tópico para ter os labels na mesma tabela
df_ranking = df_scores.merge(df_topic_info[['topic_id', 'label']], on='topic_id', how='left')
df_ranking = df_ranking.sort_values(by='trend_score', ascending=False).reset_index(drop=True)

# -----------------------------------------------------------------------------
# Task 2: Painel Principal (Lista Ranqueada)
# -----------------------------------------------------------------------------
st.header("🔥 Em Alta")

# Exibição do ranking em formato de métricas (Cards) para os Top 3
col1, col2, col3 = st.columns(3)
top_cols = [col1, col2, col3]

for i in range(min(3, len(df_ranking))):
    with top_cols[i]:
        row = df_ranking.iloc[i]
        # Mostra o label e o score de tendência, além da taxa de crescimento como delta
        st.metric(
            label=row['label'], 
            value=f"Score: {row['trend_score']:.2f}", 
            delta=f"{row['growth']:.2%} Crescimento"
        )

st.markdown("### Tabela Completa de Ascensão")
# Formatação da tabela para exibição clara do nome legível e taxa de crescimento
st.dataframe(
    df_ranking[['topic_id', 'label', 'trend_score', 'growth']].style.format({
        'trend_score': '{:.2f}',
        'growth': '{:.2%}'
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()

# -----------------------------------------------------------------------------
# Task 3: Drill-down do Tópico
# -----------------------------------------------------------------------------
st.header("🔎 Drill-down de Tópicos")
st.markdown("Selecione um tópico para aprofundar na sua evolução, palavras-chave e artigos originais.")

# Selectbox usando o Label, mas guardando o ID do tópico para os filtros
opcoes_topicos = df_ranking.set_index('topic_id')['label'].to_dict()
topico_selecionado_id = st.selectbox(
    "Escolha o Tópico:",
    options=list(opcoes_topicos.keys()),
    format_func=lambda x: opcoes_topicos[x]
)

if topico_selecionado_id is not None:
    tab1, tab2, tab3 = st.tabs(["📈 Série Temporal", "🔠 Termos Representativos", "📰 Artigos-Fonte"])
    
    # Filtra os dados apenas para o tópico selecionado
    topic_serie = df_series[df_series['topic_id'] == topico_selecionado_id]
    topic_terms = df_topic_terms[df_topic_terms['topic_id'] == topico_selecionado_id]
    topic_articles = df_corpus[df_corpus['topic_id'] == topico_selecionado_id]
    
    # Aba 1: Gráfico Temporal
    with tab1:
        if not topic_serie.empty:
            # Assumindo que a série temporal tem colunas 'date' e 'volume' (ou similar)
            # Adapte 'date' e 'volume' caso as colunas no parquet tenham nomes diferentes
            time_col = 'date' if 'date' in topic_serie.columns else topic_serie.columns[1]
            val_col = 'volume' if 'volume' in topic_serie.columns else topic_serie.columns[2]
            
            fig = px.line(
                topic_serie, 
                x=time_col, 
                y=val_col,
                title=f"Evolução no Tempo: {opcoes_topicos[topico_selecionado_id]}",
                markers=True
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados temporais para exibir.")
            
    # Aba 2: Termos Representativos (c-TF-IDF)
    with tab2:
        if not topic_terms.empty:
            st.markdown("Termos mais relevantes que compõem este assunto:")
            # Assumindo que o dataframe tenha 'term' e 'weight'
            term_col = 'term' if 'term' in topic_terms.columns else topic_terms.columns[1]
            weight_col = 'weight' if 'weight' in topic_terms.columns else topic_terms.columns[2]
            
            st.dataframe(
                topic_terms[[term_col, weight_col]].sort_values(by=weight_col, ascending=False),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Termos não disponíveis.")
            
    # Aba 3: Artigos Fonte
    with tab3:
        if not topic_articles.empty:
            st.markdown(f"**{len(topic_articles)} artigos** relacionados encontrados:")
            
            # Assumindo que corpus tem 'title' e 'url'
            title_col = 'title' if 'title' in topic_articles.columns else topic_articles.columns[0]
            url_col = 'url' if 'url' in topic_articles.columns else topic_articles.columns[1]
            
            for _, artigo in topic_articles.iterrows():
                titulo = artigo.get(title_col, "Sem título")
                link = artigo.get(url_col, "#")
                st.markdown(f"- [{titulo}]({link})")
        else:
            st.info("Nenhum artigo encontrado para este tópico.")
            