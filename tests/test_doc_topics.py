"""
Testes para atribuição de tópicos por documento.
"""

import pandas as pd
import tempfile
from pathlib import Path
import pytest
from src.modelagem.doc_topics import criar_doc_topics

def test_doc_topics():
    """Testa a criação da tabela doc_topics."""
    
    # Dados simulados
    doc_topics = pd.DataFrame({
        'doc_id': [1, 2, 3, 4],
        'topic_id': [0, 1, 0, -1],
        'probabilidade': [0.9, 0.8, 0.7, 0.5]
    })
    
    corpus = pd.DataFrame({
        'doc_id': [1, 2, 3, 4],
        'data': ['2024-01-01', '2024-01-02', '2024-01-03', '2024-01-04'],
        'texto_limpo': ['noticia a', 'noticia b', 'noticia c', 'noticia d']
    })
    
    topic_info = pd.DataFrame({
        'topic_id': [0, 1, -1],
        'label': ['topico0', 'topico1', 'outliers'],
        'size': [2, 1, 1],
        'first_seen_date': ['2024-01-01', '2024-01-02', '2024-01-01'],
        'last_seen_date': ['2024-01-03', '2024-01-02', '2024-01-04']
    })
    
    # Salvar temporariamente
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        
        doc_topics.to_parquet(tmp / 'doc_topics.parquet')
        corpus.to_parquet(tmp / 'corpus_clean.parquet')
        topic_info.to_parquet(tmp / 'topic_info.parquet')
        
        # Executar
        resultado = criar_doc_topics(
            caminho_doc_topics=tmp / 'doc_topics.parquet',
            caminho_corpus=tmp / 'corpus_clean.parquet',
            caminho_topic_info=tmp / 'topic_info.parquet',
            caminho_saida=tmp / 'topics'
        )
        
        # Verificar
        assert len(resultado) == 4
        assert 'doc_id' in resultado.columns
        assert 'topic_id' in resultado.columns
        assert 'data' in resultado.columns
        
        # Verificar contagens
        contagens = resultado['topic_id'].value_counts()
        assert contagens.sum() == 4
        assert contagens[0] == 2
        assert contagens[1] == 1
        assert contagens[-1] == 1

def test_doc_topics_fail_fast():
    """Testa que a função falha quando há datas faltando."""
    
    # Dados com datas faltando
    doc_topics = pd.DataFrame({
        'doc_id': [1, 2],
        'topic_id': [0, 1],
        'probabilidade': [0.9, 0.8]
    })
    
    corpus = pd.DataFrame({
        'doc_id': [1],  # doc_id 2 está faltando
        'data': ['2024-01-01'],
        'texto_limpo': ['noticia a']
    })
    
    topic_info = pd.DataFrame({
        'topic_id': [0, 1],
        'label': ['topico0', 'topico1'],
        'size': [1, 1],
        'first_seen_date': ['2024-01-01', '2024-01-01'],
        'last_seen_date': ['2024-01-01', '2024-01-01']
    })
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        
        doc_topics.to_parquet(tmp / 'doc_topics.parquet')
        corpus.to_parquet(tmp / 'corpus_clean.parquet')
        topic_info.to_parquet(tmp / 'topic_info.parquet')
        
        # Deve levantar exceção
        with pytest.raises(ValueError) as excinfo:
            criar_doc_topics(
                caminho_doc_topics=tmp / 'doc_topics.parquet',
                caminho_corpus=tmp / 'corpus_clean.parquet',
                caminho_topic_info=tmp / 'topic_info.parquet',
                caminho_saida=tmp / 'topics'
            )
        
        assert "documentos sem data" in str(excinfo.value)