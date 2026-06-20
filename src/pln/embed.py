import time
import numpy as np
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
import torch

from src.common.io import ler_parquet, salvar_parquet
from src.common.config import config

def gerar_embeddings(textos, modelo, batch_size=64):
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Dispositivo usado: {dispositivo}")
    
    print(f"Carregando modelo: {modelo}")
    model = SentenceTransformer(modelo, device=dispositivo)
    
    tamanho_embedding = model.get_sentence_embedding_dimension()
    print(f"Dimensão do embedding: {tamanho_embedding}")
    
    print(f"Processando {len(textos)} textos em lotes de {batch_size}...")
    inicio = time.time()
    
    embeddings = model.encode(
        textos,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True
    )
    
    fim = time.time()
    tempo_total = fim - inicio
    
    print(f"Embeddings gerados em {tempo_total:.2f} segundos")
    print(f"Formato dos embeddings: {embeddings.shape}")
    
    return embeddings, tempo_total, dispositivo

def embed_corpus(caminho_entrada=None, caminho_saida=None, modelo=None, batch_size=None):
    if caminho_entrada is None:
        caminho_entrada = Path("dados/processed/corpus_clean.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/processed")
    
    if modelo is None:
        modelo = config.embedding.model_name
    
    if batch_size is None:
        batch_size = config.embedding.batch_size
    
    print("=" * 60)
    print("INICIANDO GERAÇÃO DE EMBEDDINGS")
    print("=" * 60)
    
    print(f"\n1. Carregando corpus de: {caminho_entrada}")
    df_corpus = ler_parquet(caminho_entrada)
    print(f"   -> {len(df_corpus)} artigos carregados")
    
    textos = df_corpus['texto_limpo'].tolist()
    doc_ids = df_corpus['doc_id'].tolist()
    
    print(f"\n2. Gerando embeddings...")
    embeddings, tempo_total, dispositivo = gerar_embeddings(
        textos, 
        modelo, 
        batch_size
    )
    
    print(f"\n3. Salvando resultados...")
    
    caminho_embeddings = caminho_saida / "embeddings.npy"
    np.save(caminho_embeddings, embeddings.astype("float32"))
    print(f"   -> Embeddings salvos em: {caminho_embeddings}")
    print(f"   -> Tamanho: {embeddings.nbytes / 1024 / 1024:.2f} MB")
    
    df_index = pd.DataFrame({
        'doc_id': doc_ids,
        'row_idx': range(len(doc_ids))
    })
    
    caminho_index = caminho_saida / "embeddings_index.parquet"
    salvar_parquet(df_index, caminho_index)
    print(f"   -> Índice salvo em: {caminho_index}")
    
    assert embeddings.shape[0] == len(df_corpus), "Erro: número de embeddings não bate com o corpus"
    assert len(df_index) == len(df_corpus), "Erro: índice não bate com o corpus"
    print(f"\n   -> Verificação de alinhamento: OK")
    
    print(f"\n4. Tempo total: {tempo_total:.2f} segundos")
    
    import json
    from datetime import datetime
    
    manifest = {
        "data": datetime.now().isoformat(),
        "modelo": modelo,
        "dispositivo": dispositivo,
        "batch_size": batch_size,
        "total_artigos": len(df_corpus),
        "dimensao_embedding": embeddings.shape[1],
        "tempo_segundos": tempo_total,
        "tamanho_mb": embeddings.nbytes / 1024 / 1024,
        "arquivo_embeddings": str(caminho_embeddings),
        "arquivo_index": str(caminho_index)
    }
    
    caminho_manifest = caminho_saida / "run_manifest.json"
    with open(caminho_manifest, 'w') as f:
        json.dump(manifest, f, indent=2)
    print(f"   -> Manifesto salvo em: {caminho_manifest}")
    
    print("\n" + "=" * 60)
    print("EMBEDDINGS GERADOS COM SUCESSO!")
    print("=" * 60)
    
    return embeddings, df_index

def main():
    embed_corpus()

if __name__ == "__main__":
    main()