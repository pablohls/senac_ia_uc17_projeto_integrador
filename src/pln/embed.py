"""
Módulo para gerar embeddings dos textos usando Sentence-Transformers.
Transforma cada notícia em um vetor de números que representa seu significado.
"""

import time
import numpy as np
import pandas as pd
from pathlib import Path
from sentence_transformers import SentenceTransformer
import torch

from src.common.io import ler_parquet, salvar_parquet
from src.common.config import Config

def gerar_embeddings(textos, modelo, batch_size=64):
    """
    Gera embeddings para uma lista de textos usando GPU.
    
    O que faz:
    1. Carrega o modelo na GPU (ou CPU se não tiver GPU)
    2. Processa os textos em lotes (batch)
    3. Retorna um array de números (embeddings)
    
    Args:
        textos: Lista de strings (textos limpos)
        modelo: Nome do modelo Sentence-Transformer
        batch_size: Quantos textos processar por vez
        
    Returns:
        embeddings: Array numpy com os vetores
        tempo_total: Tempo gasto em segundos
        dispositivo: 'cuda' ou 'cpu'
    """
    
    # Verificar se tem GPU disponível
    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Dispositivo usado: {dispositivo}")
    
    # Carregar o modelo
    print(f"Carregando modelo: {modelo}")
    model = SentenceTransformer(modelo, device=dispositivo)
    
    # Mostrar tamanho do embedding
    tamanho_embedding = model.get_sentence_embedding_dimension()
    print(f"Dimensão do embedding: {tamanho_embedding}")
    
    # Gerar embeddings em lote
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
    """
    Função principal que orquestra o processo de embeddings.
    
    Passos:
    1. Carregar o corpus limpo
    2. Gerar embeddings em GPU
    3. Salvar os embeddings e o índice alinhado
    4. Registrar o tempo
    """
    
    # Definir caminhos padrão
    if caminho_entrada is None:
        caminho_entrada = Path("dados/processed/corpus_clean.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/processed")
    
    if modelo is None:
        modelo = Config.embedding_model
    
    if batch_size is None:
        batch_size = Config.batch_size
    
    print("=" * 60)
    print("INICIANDO GERAÇÃO DE EMBEDDINGS")
    print("=" * 60)
    
    # Passo 1: Carregar corpus limpo
    print(f"\n1. Carregando corpus de: {caminho_entrada}")
    df_corpus = ler_parquet(caminho_entrada)
    print(f"   → {len(df_corpus)} artigos carregados")
    
    # Extrair textos e doc_ids
    textos = df_corpus['texto_limpo'].tolist()
    doc_ids = df_corpus['doc_id'].tolist()
    
    # Passo 2: Gerar embeddings
    print(f"\n2. Gerando embeddings...")
    embeddings, tempo_total, dispositivo = gerar_embeddings(
        textos, 
        modelo, 
        batch_size
    )
    
    # Passo 3: Salvar embeddings e índice
    print(f"\n3. Salvando resultados...")
    
    # Salvar embeddings como .npy
    caminho_embeddings = caminho_saida / "embeddings.npy"
    np.save(caminho_embeddings, embeddings.astype("float32"))
    print(f"   → Embeddings salvos em: {caminho_embeddings}")
    print(f"   → Tamanho: {embeddings.nbytes / 1024 / 1024:.2f} MB")
    
    # Criar e salvar o índice (doc_id -> linha)
    df_index = pd.DataFrame({
        'doc_id': doc_ids,
        'row_idx': range(len(doc_ids))
    })
    
    caminho_index = caminho_saida / "embeddings_index.parquet"
    salvar_parquet(df_index, caminho_index)
    print(f"   → Índice salvo em: {caminho_index}")
    
    # Verificar alinhamento
    assert embeddings.shape[0] == len(df_corpus), "Erro: número de embeddings não bate com o corpus"
    assert len(df_index) == len(df_corpus), "Erro: índice não bate com o corpus"
    print(f"\n   ✓ Verificação de alinhamento: OK")
    
    # Passo 4: Registrar tempo
    print(f"\n4. Tempo total: {tempo_total:.2f} segundos")
    
    # Salvar manifest com informações
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
    print(f"   → Manifesto salvo em: {caminho_manifest}")
    
    print("\n" + "=" * 60)
    print("EMBEDDINGS GERADOS COM SUCESSO!")
    print("=" * 60)
    
    return embeddings, df_index

def main():
    """Ponto de entrada do script."""
    embed_corpus()

if __name__ == "__main__":
    main()
