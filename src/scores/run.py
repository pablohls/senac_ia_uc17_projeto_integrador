"""
Runner principal da Fase 2 - executa limpeza, embeddings e clustering.
Uso: python -m src.pln.run
"""

import sys
from pathlib import Path
import time
from datetime import datetime

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.common.io import ler_parquet, salvar_parquet
from src.pln.clean import aplicar_limpeza_corpus
from src.pln.embed import embed_corpus
from src.modelagem.topics import modelar_topicos
from src.modelagem.doc_topics import criar_doc_topics

def executar_limpeza():
    """Executa a limpeza do corpus."""
    print("\n" + "=" * 60)
    print("ETAPA 1: LIMPEZA DO CORPUS")
    print("=" * 60)
    
    caminho_entrada = Path("dados/raw/corpus.parquet")
    caminho_saida = Path("dados/processed/corpus_clean.parquet")
    
    if not caminho_entrada.exists():
        print(f"ERRO: {caminho_entrada} não encontrado!")
        return False
    
    df_raw = ler_parquet(caminho_entrada)
    print(f"Carregados {len(df_raw)} artigos")
    
    df_clean = aplicar_limpeza_corpus(df_raw)
    print(f"Mantidos {len(df_clean)} artigos")
    
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    salvar_parquet(df_clean, caminho_saida)
    print(f"Salvo em {caminho_saida}")
    
    return True

def executar_embeddings():
    """Executa a geração de embeddings."""
    print("\n" + "=" * 60)
    print("ETAPA 2: GERAÇÃO DE EMBEDDINGS")
    print("=" * 60)
    
    embed_corpus()
    return True

def executar_clustering():
    """Executa o clustering e criação de tópicos."""
    print("\n" + "=" * 60)
    print("ETAPA 3: CLUSTERING E TÓPICOS")
    print("=" * 60)
    
    modelar_topicos()
    return True

def executar_doc_topics():
    """Executa a atribuição final de tópicos por documento."""
    print("\n" + "=" * 60)
    print("ETAPA 4: ATRIBUIÇÃO DE TÓPICOS")
    print("=" * 60)
    
    criar_doc_topics()
    return True

def main():
    """Executa toda a pipeline da Fase 2."""
    print("=" * 60)
    print("INICIANDO PIPELINE DA FASE 2")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    inicio_total = time.time()
    
    etapas = [
        ("Limpeza", executar_limpeza),
        ("Embeddings", executar_embeddings),
        ("Clustering", executar_clustering),
        ("Doc Topics", executar_doc_topics)
    ]
    
    for nome, funcao in etapas:
        try:
            if not funcao():
                print(f"\nERRO: Falha na etapa {nome}")
                return
        except Exception as e:
            print(f"\nERRO na etapa {nome}: {e}")
            return
    
    fim_total = time.time()
    
    print("\n" + "=" * 60)
    print("PIPELINE DA FASE 2 CONCLUÍDA COM SUCESSO!")
    print(f"Tempo total: {fim_total - inicio_total:.2f} segundos")
    print("=" * 60)

if __name__ == "__main__":
    main()