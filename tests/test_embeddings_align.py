"""
Teste de alinhamento dos embeddings.
"""

import numpy as np
import pandas as pd
from pathlib import Path

def test_embeddings_align():
    """Verifica se embeddings, índice e corpus estão alinhados."""
    try:
        emb = np.load('dados/processed/embeddings.npy')
        idx = pd.read_parquet('dados/processed/embeddings_index.parquet')
        corpus = pd.read_parquet('dados/processed/corpus_clean.parquet')
    except FileNotFoundError:
        print("Arquivos não encontrados - pule este teste")
        return
    
    # Verificar alinhamento
    assert emb.shape[0] == len(idx) == len(corpus), "Alinhamento quebrado!"
    
    # Verificar que doc_ids são únicos
    assert len(idx['doc_id'].unique()) == len(idx), "doc_ids duplicados!"
    
    # Verificar que row_idx estão em ordem
    assert list(idx['row_idx']) == list(range(len(idx))), "row_idx fora de ordem!"
    
    print("✅ Teste de alinhamento passou!")