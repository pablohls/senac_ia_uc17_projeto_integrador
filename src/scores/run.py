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
from src.scores.trend_score import trend_score_l1
from src.scores.forecast import calcular_surpresa_l2, salvar_alertas

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

     # Step 4: Story 3.2 — Trend Score Camada 1
    logger.info("\n--- Story 3.2: Trend Score Camada 1 (estatístico) ---")
    try:
        scores = trend_score_l1(series, config.trend_score)
        logger.info(f"  ✓ Scores calculados: {len(scores)} tópicos")
        
        # Log top 5
        top_5 = scores.head(5)
        logger.info("  Top 5 tendências:")
        for _, row in top_5.iterrows():
            badge = "[NOVO]" if row["is_new"] else ""
            logger.info(f"    - Tópico {row['topic_id']}: score={row['trend_score']:.2f} {badge}")

        # Persiste
        output_path = salvar_parquet(scores, "dados/scores/scores.parquet")
        logger.info(f"  ✓ Persistido: {output_path}")

    except Exception as e:
        logger.error(f"  ✗ Erro na Story 3.2: {e}", exc_info=True)
        raise
    
    # Step 5: Story 3.3 — Trend Score Camada 2 (LSTM + Surpresa)
    logger.info("\n--- Story 3.3: Trend Score Camada 2 (LSTM + Surpresa) ---")
    try:
        scores_l2, alerts = calcular_surpresa_l2(series, scores, config.trend_score)
        if alerts:
            logger.info(f"  ⚠ {len(alerts)} anomalias detectadas!")
            salvar_alertas(alerts)
        
        output_path = salvar_parquet(scores_l2, "dados/scores/scores.parquet")
        logger.info(f"  ✓ Persistido (L1+L2): {output_path}")
    except Exception as e:
        logger.warning(f"  ⚠ Camada 2 falhou (degradação graciosa): {e}")

if __name__ == "__main__":
    main()