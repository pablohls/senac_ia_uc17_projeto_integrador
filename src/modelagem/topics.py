import numpy as np
import pandas as pd
from pathlib import Path
from bertopic import BERTopic
from umap import UMAP
from hdbscan import HDBSCAN
from sklearn.feature_extraction.text import CountVectorizer
import time
import json
from datetime import datetime

from src.common.io import ler_parquet, salvar_parquet

def configurar_modelo(min_topic_size=2, n_neighbors=15, min_cluster_size=2):
    umap_model = UMAP(
        n_neighbors=n_neighbors,
        n_components=5,
        min_dist=0.0,
        metric='cosine',
        random_state=42
    )
    
    hdbscan_model = HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric='euclidean',
        cluster_selection_epsilon=0.1,
        prediction_data=True
    )
    
    vectorizer_model = CountVectorizer(
        stop_words="english",
        min_df=1,
        ngram_range=(1, 2)
    )
    
    model = BERTopic(
        embedding_model=None,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        min_topic_size=min_topic_size,
        calculate_probabilities=True,
        verbose=True
    )
    
    return model

def modelar_topicos(caminho_embeddings=None, caminho_index=None, caminho_corpus=None, 
                    caminho_saida=None, min_topic_size=2):
    
    if caminho_embeddings is None:
        caminho_embeddings = Path("dados/processed/embeddings.npy")
    
    if caminho_index is None:
        caminho_index = Path("dados/processed/embeddings_index.parquet")
    
    if caminho_corpus is None:
        caminho_corpus = Path("dados/processed/corpus_clean.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/processed")
    
    print("=" * 60)
    print("INICIANDO MODELAGEM DE TOPICOS")
    print("=" * 60)
    
    print("\n1. Carregando dados...")
    embeddings = np.load(caminho_embeddings)
    print(f"   Embeddings: {embeddings.shape}")
    
    df_index = ler_parquet(caminho_index)
    print(f"   Indice: {len(df_index)} linhas")
    
    df_corpus = ler_parquet(caminho_corpus)
    print(f"   Corpus: {len(df_corpus)} linhas")
    
    assert len(df_index) == len(df_corpus) == embeddings.shape[0]
    
    print("\n2. Configurando BERTopic...")
    model = configurar_modelo(min_topic_size=min_topic_size)
    
    print("\n3. Executando clustering...")
    inicio = time.time()
    
    textos = df_corpus['texto_limpo'].tolist()
    topicos, probabilities = model.fit_transform(textos, embeddings=embeddings)
    
    fim = time.time()
    tempo_total = fim - inicio
    print(f"   Concluido em {tempo_total:.2f} segundos")
    
    print("\n4. Extraindo informacoes dos topicos...")
    topic_info = model.get_topic_info()
    print(f"   {len(topic_info)} topicos encontrados")
    
    n_topicos = len(topic_info[topic_info['Topic'] != -1])
    n_outliers = len(topic_info[topic_info['Topic'] == -1])
    print(f"   Topicoss: {n_topicos}, Outliers: {n_outliers}")
    
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
    print(f"   {len(df_topic_terms)} termos extraidos")
    
    print("\n5. Adicionando metadados...")
    from datetime import timedelta
    hoje = datetime.now()
    topic_info['first_seen_date'] = hoje - timedelta(days=7)
    topic_info['last_seen_date'] = hoje
    
    topic_info['label'] = topic_info.apply(
        lambda row: model.get_topic(row['Topic'])[0][0] if row['Topic'] != -1 else "Outliers",
        axis=1
    )
    
    print("\n6. Salvando resultados...")
    
    caminho_topic_info = caminho_saida / "topic_info.parquet"
    salvar_parquet(topic_info, caminho_topic_info)
    print(f"   Topic info: {caminho_topic_info}")
    
    caminho_topic_terms = caminho_saida / "topic_terms.parquet"
    salvar_parquet(df_topic_terms, caminho_topic_terms)
    print(f"   Topic terms: {caminho_topic_terms}")
    
    df_doc_topics = pd.DataFrame({
        'doc_id': df_corpus['doc_id'].values,
        'topic_id': topicos,
        'probabilidade': probabilities.max(axis=1) if probabilities is not None else 0
    })
    caminho_doc_topics = caminho_saida / "doc_topics.parquet"
    salvar_parquet(df_doc_topics, caminho_doc_topics)
    print(f"   Doc topics: {caminho_doc_topics}")
    
    manifest = {
        "data": datetime.now().isoformat(),
        "min_topic_size": min_topic_size,
        "n_neighbors": 15,
        "min_cluster_size": 2,
        "total_artigos": len(df_corpus),
        "n_topicos": n_topicos,
        "n_outliers": n_outliers,
        "tempo_segundos": tempo_total
    }
    
    caminho_manifest = caminho_saida / "topic_manifest.json"
    with open(caminho_manifest, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"   Manifesto: {caminho_manifest}")
    
    print("\n" + "=" * 60)
    print("MODELAGEM DE TOPICOS CONCLUIDA!")
    print("=" * 60)
    
    print("\nResumo dos topicos:")
    for topic_id in topic_info['Topic'].values:
        if topic_id != -1:
            termos = model.get_topic(topic_id)[:5]
            nomes = [t[0] for t in termos]
            print(f"   Topico {topic_id}: {', '.join(nomes)}")
    
    return model, topic_info, df_topic_terms

def main():
    modelar_topicos()

if __name__ == "__main__":
    main()