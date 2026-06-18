"""
Módulo para análise temporal dos tópicos.
Cria séries de frequência por tópico ao longo do tempo.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json

from src.common.io import ler_parquet, salvar_parquet

def criar_serie_temporal(caminho_doc_topics=None, caminho_corpus=None, 
                          caminho_topic_info=None, caminho_saida=None):
    
    if caminho_doc_topics is None:
        caminho_doc_topics = Path("dados/topics/doc_topics.parquet")
    
    if caminho_corpus is None:
        caminho_corpus = Path("dados/processed/corpus_clean.parquet")
    
    if caminho_topic_info is None:
        caminho_topic_info = Path("dados/topics/topic_info.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/temporal")
    
    print("=" * 60)
    print("CRIANDO SÉRIE TEMPORAL DE TÓPICOS")
    print("=" * 60)
    
    print("\n1. Carregando dados...")
    
    df_doc = ler_parquet(caminho_doc_topics)
    print(f"   Doc topics: {len(df_doc)} documentos")
    
    df_corpus = ler_parquet(caminho_corpus)
    print(f"   Corpus: {len(df_corpus)} documentos")
    
    print("\n2. Preparando dados...")
    
    # CORREÇÃO: Converter data do corpus para datetime
    if 'data' in df_corpus.columns:
        # Tentar converter para datetime
        df_corpus['data'] = pd.to_datetime(df_corpus['data'], errors='coerce')
        # Criar coluna de string
        df_corpus['data_str'] = df_corpus['data'].dt.strftime('%Y-%m-%d')
        print(f"   Datas do corpus convertidas")
    else:
        # Criar datas fictícias
        print("   Corpus sem data. Criando datas fictícias...")
        hoje = datetime.now()
        df_corpus['data'] = [hoje - timedelta(days=i%30) for i in range(len(df_corpus))]
        df_corpus['data_str'] = df_corpus['data'].dt.strftime('%Y-%m-%d')
    
    # Juntar doc_topics com corpus para obter data
    if 'data' not in df_doc.columns:
        df = df_doc.merge(df_corpus[['doc_id', 'data_str']], on='doc_id', how='left')
        df['data'] = pd.to_datetime(df['data_str'])
        df = df.drop('data_str', axis=1)
    else:
        df = df_doc.copy()
        df['data'] = pd.to_datetime(df['data'])
    
    # Verificar se tem dados com data
    df = df.dropna(subset=['data'])
    
    print(f"   Total: {len(df)} documentos com data")
    
    if len(df) == 0:
        print("   ERRO: Nenhum documento com data válida!")
        return None, None
    
    data_min = df['data'].min()
    data_max = df['data'].max()
    print(f"   Período: {data_min.date()} a {data_max.date()}")
    print(f"   Total de dias: {(data_max - data_min).days + 1}")
    
    print("\n3. Agrupando por data e tópico...")
    
    # Criar coluna de data como string para agrupamento
    df['data_str'] = df['data'].dt.strftime('%Y-%m-%d')
    
    # Agrupar
    serie = df.groupby(['data_str', 'topic_id']).size().reset_index(name='count')
    serie.columns = ['data', 'topic_id', 'count']
    
    # Converter data de volta para datetime
    serie['data'] = pd.to_datetime(serie['data'])
    
    topicos = sorted(serie['topic_id'].unique())
    print(f"   Tópicos encontrados: {topicos}")
    
    print("\n4. Preenchendo dias sem dados...")
    
    # Criar todos os dias do período
    todos_os_dias = pd.date_range(start=data_min.date(), end=data_max.date(), freq='D')
    
    # Criar DataFrame completo
    df_completo = pd.DataFrame()
    for topico in topicos:
        df_topico = pd.DataFrame({
            'data': todos_os_dias,
            'topic_id': topico
        })
        df_completo = pd.concat([df_completo, df_topico])
    
    # Converter data para string para merge
    df_completo['data_str'] = df_completo['data'].dt.strftime('%Y-%m-%d')
    serie['data_str'] = serie['data'].dt.strftime('%Y-%m-%d')
    
    # Fazer merge
    df_completo = df_completo.merge(
        serie[['data_str', 'topic_id', 'count']], 
        on=['data_str', 'topic_id'], 
        how='left'
    )
    df_completo['count'] = df_completo['count'].fillna(0).astype(int)
    df_completo = df_completo.drop('data_str', axis=1)
    
    print(f"   Série criada: {len(df_completo)} linhas")
    
    print("\n5. Adicionando nomes dos tópicos...")
    
    if caminho_topic_info.exists():
        topic_info = ler_parquet(caminho_topic_info)
        topic_labels = dict(zip(topic_info['topic_id'], topic_info['label']))
        df_completo['label'] = df_completo['topic_id'].map(topic_labels)
    else:
        df_completo['label'] = df_completo['topic_id'].astype(str)
    
    df_completo['label'] = df_completo['label'].fillna(df_completo['topic_id'].astype(str))
    print(f"   Labels adicionadas")
    
    print("\n6. Calculando métricas adicionais...")
    
    df_completo = df_completo.sort_values(['topic_id', 'data'])
    df_completo['media_movel_7d'] = df_completo.groupby('topic_id')['count'].transform(
        lambda x: x.rolling(7, min_periods=1).mean()
    )
    df_completo['total_acumulado'] = df_completo.groupby('topic_id')['count'].cumsum()
    
    print("   Métricas calculadas")
    
    print("\n7. Salvando resultados...")
    
    caminho_saida.mkdir(parents=True, exist_ok=True)
    
    caminho_serie = caminho_saida / "serie_temporal.parquet"
    salvar_parquet(df_completo, caminho_serie)
    print(f"   Série temporal salva em: {caminho_serie}")
    
    resumo = df_completo.groupby('topic_id').agg({
        'count': ['sum', 'mean', 'max'],
        'data': ['min', 'max']
    }).round(2)
    resumo.columns = ['total', 'media_diaria', 'maximo_diario', 'primeiro_dia', 'ultimo_dia']
    
    if 'topic_labels' in locals():
        resumo['label'] = resumo.index.map(lambda x: topic_labels.get(x, str(x)))
    else:
        resumo['label'] = resumo.index.astype(str)
    
    resumo = resumo[['label', 'total', 'media_diaria', 'maximo_diario', 'primeiro_dia', 'ultimo_dia']]
    
    caminho_resumo = caminho_saida / "resumo_temporal.parquet"
    salvar_parquet(resumo, caminho_resumo)
    print(f"   Resumo salvo em: {caminho_resumo}")
    
    print("\n8. Gerando relatório...")
    
    relatorio = {
        "data_execucao": datetime.now().isoformat(),
        "total_documentos": len(df),
        "periodo_inicio": data_min.isoformat(),
        "periodo_fim": data_max.isoformat(),
        "total_dias": (data_max - data_min).days + 1,
        "topicos": [
            {
                "topic_id": int(t),
                "label": str(topic_labels.get(t, t)) if 'topic_labels' in locals() else str(t),
                "total": int(resumo.loc[t, 'total']) if t in resumo.index else 0,
                "media_diaria": float(resumo.loc[t, 'media_diaria']) if t in resumo.index else 0
            }
            for t in topicos
        ]
    }
    
    caminho_relatorio = caminho_saida / "relatorio_temporal.json"
    with open(caminho_relatorio, 'w') as f:
        json.dump(relatorio, f, indent=2)
    print(f"   Relatório salvo em: {caminho_relatorio}")
    
    print("\n" + "=" * 60)
    print("SÉRIE TEMPORAL CRIADA COM SUCESSO!")
    print("=" * 60)
    
    print("\nResumo por tópico:")
    print(resumo.to_string())
    
    return df_completo, resumo

def main():
    criar_serie_temporal()

if __name__ == "__main__":
    main()
