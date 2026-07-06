"""
Módulo para clustering e nomeação de tópicos usando BERTopic.
Agrupa notícias por assunto e extrai palavras que caracterizam cada grupo.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from bertopic import BERTopic
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
import time

from src.common.io import ler_parquet, salvar_parquet, atualizar_manifest
from src.common.config import config

def configurar_modelo(params=None):
    """
    Configura o BERTopic com os parâmetros de `config.clustering` (Story 2.3).

    Argumentos:
        params: instância de ClusteringParams; se None, usa `config.clustering`

    Retorna:
        Modelo BERTopic configurado
    """
    if params is None:
        params = config.clustering

    # UMAP reduz a dimensão dos embeddings
    umap_model = UMAP(
        n_neighbors=params.n_neighbors,
        n_components=params.n_components,
        min_dist=0.0,
        metric='cosine',
        random_state=params.random_state
    )

    # HDBSCAN encontra os grupos
    hdbscan_model = HDBSCAN(
        min_cluster_size=params.min_cluster_size,
        metric='euclidean',
        cluster_selection_epsilon=params.cluster_selection_epsilon,
        prediction_data=True
    )

    # Stopwords em português (F2)
    try:
        import nltk
        from nltk.corpus import stopwords
        nltk.download('stopwords', quiet=True)
        stopwords_pt = stopwords.words('portuguese')
        print(f"   Stopwords PT carregadas: {len(stopwords_pt)} palavras")
    except Exception as e:
        print(f"   Aviso: NLTK não disponível ({e}), usando stopwords padrão")
        stopwords_pt = []
    
    # CountVectorizer extrai palavras dos textos
    vectorizer_model = CountVectorizer(
        stop_words=stopwords_pt,
        min_df=1,
        ngram_range=(1, 2)
    )

    # BERTopic combina tudo
    # language="multilingual" é OBRIGATÓRIO: o default ("english") faz o
    # _preprocess_text interno remover caracteres não-ASCII — os acentos do
    # PT-BR sumiam dos termos c-TF-IDF ("missão" virava "misso").
    model = BERTopic(
        language="multilingual",
        embedding_model=None,  # Usamos embeddings prontos
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        min_topic_size=params.min_topic_size,
        calculate_probabilities=True,
        verbose=True
    )

    return model

def modelar_topicos(caminho_embeddings=None, caminho_index=None, caminho_corpus=None,
                    caminho_saida=None, params=None):
    """
    Função principal que executa o clustering.

    Argumentos:
        caminho_embeddings: Caminho do arquivo embeddings.npy
        caminho_index: Caminho do embeddings_index.parquet
        caminho_corpus: Caminho do corpus_clean.parquet
        caminho_saida: Pasta para salvar os resultados
        params: ClusteringParams; se None, usa `config.clustering`
    """
    if params is None:
        params = config.clustering

    # Define caminhos padrão
    if caminho_embeddings is None:
        caminho_embeddings = Path("dados/processed/embeddings.npy")
    
    if caminho_index is None:
        caminho_index = Path("dados/processed/embeddings_index.parquet")
    
    if caminho_corpus is None:
        caminho_corpus = Path("dados/processed/corpus_clean.parquet")
    
    # CORREÇÃO: salvar em dados/topics/ (F7)
    if caminho_saida is None:
        caminho_saida = Path("dados/topics")
    
    print("=" * 60)
    print("INICIANDO MODELAGEM DE TÓPICOS")
    print("=" * 60)
    
    # Passo 1: Carregar dados
    print("\n1. Carregando dados...")
    embeddings = np.load(caminho_embeddings)
    print(f"   Embeddings: {embeddings.shape}")
    
    df_index = ler_parquet(caminho_index)
    print(f"   Índice: {len(df_index)} linhas")
    
    df_corpus = ler_parquet(caminho_corpus)
    print(f"   Corpus: {len(df_corpus)} linhas")
    
    # Verifica alinhamento
    assert len(df_index) == len(df_corpus) == embeddings.shape[0], \
        "Erro: dados não estão alinhados!"
    
    # Passo 2: Configurar BERTopic
    print("\n2. Configurando BERTopic...")
    print(f"   Parâmetros (config.yaml): {params.model_dump()}")
    model = configurar_modelo(params=params)
    
    # Passo 3: Executar clustering
    print("\n3. Executando clustering...")
    inicio = time.time()
    
    # Extrai textos na mesma ordem dos embeddings
    textos = df_corpus['texto_limpo'].tolist()
    
    # fit_transform executa o clustering e atribui tópicos
    topicos, probabilities = model.fit_transform(textos, embeddings=embeddings)
    
    fim = time.time()
    tempo_total = fim - inicio
    print(f"   Concluído em {tempo_total:.2f} segundos")
    
    # Passo 4: Extrair informações dos tópicos
    print("\n4. Extraindo informações dos tópicos...")
    topic_info = model.get_topic_info()
    print(f"   {len(topic_info)} tópicos encontrados")
    
    n_topicos = len(topic_info[topic_info['Topic'] != -1])
    n_outliers = len(topic_info[topic_info['Topic'] == -1])
    print(f"   Tópicos: {n_topicos}, Outliers: {n_outliers}")
    
    # Extrai termos de cada tópico
    topic_terms_list = []
    for topic_id in topic_info['Topic'].values:
        termos = model.get_topic(topic_id)
        if termos:
            for rank, (termo, peso) in enumerate(termos, 1):
                topic_terms_list.append({
                    'topic_id': topic_id,
                    'term': termo,
                    'ctfidf_weight': peso,
                    'rank': rank
                })
    
    df_topic_terms = pd.DataFrame(topic_terms_list)
    print(f"   {len(df_topic_terms)} termos extraídos")
    
    # Passo 5: Adicionar metadados
    print("\n5. Adicionando metadados...")
    
    # CORREÇÃO: datas first_seen/last_seen a partir dos documentos reais (F6)
    df_doc_topics = pd.DataFrame({
        'doc_id': df_corpus['doc_id'].values,
        'topic_id': topicos
    })
    
    # Juntar com as datas do corpus
    df_com_datas = df_doc_topics.merge(
        df_corpus[['doc_id', 'data']], 
        on='doc_id'
    )
    
    # Calcular first_seen (min) e last_seen (max) por tópico
    datas_por_topico = df_com_datas.groupby('topic_id')['data'].agg(['min', 'max'])
    
    # Label com top-N termos (F11) — N vem da config
    def criar_label(topic_id, model):
        if topic_id == -1:
            return "Outliers"
        termos = model.get_topic(topic_id)[:params.label_top_n]
        return " ".join([t[0] for t in termos])
    
    # CORREÇÃO: schema A3 (F4)
    topic_info = topic_info.rename(columns={
        'Topic': 'topic_id',
        'Count': 'size'
    })
    
    # Adicionar label
    topic_info['label'] = topic_info['topic_id'].apply(
        lambda tid: criar_label(tid, model)
    )
    
    # Adicionar datas
    topic_info['first_seen_date'] = topic_info['topic_id'].map(datas_por_topico['min'])
    topic_info['last_seen_date'] = topic_info['topic_id'].map(datas_por_topico['max'])
    
    # Para outliers (-1), usar a data mais antiga e mais nova
    if -1 in topic_info['topic_id'].values:
        topic_info.loc[topic_info['topic_id'] == -1, 'first_seen_date'] = datas_por_topico['min'].min()
        topic_info.loc[topic_info['topic_id'] == -1, 'last_seen_date'] = datas_por_topico['max'].max()
    
    # Selecionar apenas as colunas do contrato A3
    topic_info = topic_info[['topic_id', 'label', 'size', 
                             'first_seen_date', 'last_seen_date']]
    
    print(f"   {len(topic_info)} tópicos no schema A3")
    
    # Passo 6: Salvar resultados
    print("\n6. Salvando resultados...")
    
    # Criar pasta se não existir
    caminho_saida.mkdir(parents=True, exist_ok=True)
    
    # Salvar topic_info
    caminho_topic_info = caminho_saida / "topic_info.parquet"
    salvar_parquet(topic_info, caminho_topic_info)
    print(f"   Topic info: {caminho_topic_info}")
    
    # Salvar topic_terms
    caminho_topic_terms = caminho_saida / "topic_terms.parquet"
    salvar_parquet(df_topic_terms, caminho_topic_terms)
    print(f"   Topic terms: {caminho_topic_terms}")
    
    # Salvar doc_topics no contrato A3: {doc_id, data, topic_id, probabilidade}
    # (a coluna `data` vem do corpus — evita re-joins nos consumidores da Fase 3)
    df_doc_topics_final = pd.DataFrame({
        'doc_id': df_corpus['doc_id'].values,
        'data': df_corpus['data'].values,
        'topic_id': topicos,
        'probabilidade': probabilities.max(axis=1) if probabilities is not None else 0
    })
    caminho_doc_topics = caminho_saida / "doc_topics.parquet"
    salvar_parquet(df_doc_topics_final, caminho_doc_topics)
    print(f"   Doc topics: {caminho_doc_topics}")

    # Manifesto transversal de reprodutibilidade (F9 — contrato A1)
    atualizar_manifest(
        "clustering",
        n_docs=len(df_corpus),
        stage_version="2.3",
        params={"clustering": params.model_dump()},
        extras={"n_topics": n_topicos},
    )
    print(f"   Manifesto transversal atualizado (estágio: clustering)")
    
    print("\n" + "=" * 60)
    print("MODELAGEM DE TÓPICOS CONCLUÍDA!")
    print("=" * 60)
    
    # Mostra resumo dos tópicos
    print("\nResumo dos tópicos:")
    for topic_id in topic_info['topic_id'].values:
        if topic_id != -1:
            termos = model.get_topic(topic_id)[:5]
            nomes = [t[0] for t in termos]
            print(f"   Tópico {topic_id}: {', '.join(nomes)}")
    
    return model, topic_info, df_topic_terms

def main():
    """Ponto de entrada do script."""
    modelar_topicos()

if __name__ == "__main__":
    main()