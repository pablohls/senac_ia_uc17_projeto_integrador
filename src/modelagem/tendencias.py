"""
Módulo para detecção de tendências e tópicos emergentes.
Analisa as séries temporais para identificar padrões.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import json
from scipy import stats

from src.common.io import ler_parquet, salvar_parquet

def detectar_tendencias(caminho_serie=None, caminho_saida=None):
    """
    Detecta tendências e tópicos emergentes a partir da série temporal.
    """
    
    if caminho_serie is None:
        caminho_serie = Path("dados/temporal/serie_temporal.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/temporal")
    
    print("=" * 60)
    print("DETECTANDO TENDÊNCIAS E TÓPICOS EMERGENTES")
    print("=" * 60)
    
    print("\n1. Carregando série temporal...")
    df = ler_parquet(caminho_serie)
    print(f"   Carregados {len(df)} registros")
    
    df['data'] = pd.to_datetime(df['data'])
    
    data_min = df['data'].min()
    data_max = df['data'].max()
    print(f"   Período: {data_min.date()} a {data_max.date()}")
    
    print("\n2. Calculando métricas por tópico...")
    
    resultados = []
    
    for topic_id in df['topic_id'].unique():
        df_topic = df[df['topic_id'] == topic_id].sort_values('data')
        label = df_topic['label'].iloc[0]
        
        primeiro = df_topic['count'].iloc[0]
        ultimo = df_topic['count'].iloc[-1]
        media = df_topic['count'].mean()
        maximo = df_topic['count'].max()
        
        if primeiro > 0:
            variacao = ((ultimo - primeiro) / primeiro) * 100
        else:
            variacao = 0
        
        if len(df_topic) > 2:
            x = np.arange(len(df_topic))
            y = df_topic['count'].values
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            tendencia = slope
            correlacao = r_value
        else:
            tendencia = 0
            correlacao = 0
        
        pico_dia = df_topic.loc[df_topic['count'].idxmax(), 'data']
        pico_valor = maximo
        
        ultimos_3 = df_topic.tail(3)['count'].mean()
        
        resultados.append({
            'topic_id': int(topic_id),
            'label': str(label),
            'total': int(df_topic['count'].sum()),
            'media': round(media, 2),
            'maximo': int(maximo),
            'pico_dia': pico_dia,
            'pico_valor': int(pico_valor),
            'primeiro': int(primeiro),
            'ultimo': int(ultimo),
            'variacao_percentual': round(variacao, 2),
            'tendencia': round(tendencia, 4),
            'correlacao': round(correlacao, 4),
            'media_ultimos_3': round(ultimos_3, 2)
        })
    
    df_resultados = pd.DataFrame(resultados)
    
    print("\n3. Classificando tendências...")
    
    def classificar_tendencia(row):
        if row['variacao_percentual'] > 50:
            return "Alta forte"
        elif row['variacao_percentual'] > 20:
            return "Alta moderada"
        elif row['variacao_percentual'] < -50:
            return "Baixa forte"
        elif row['variacao_percentual'] < -20:
            return "Baixa moderada"
        else:
            return "Estável"
    
    df_resultados['classificacao'] = df_resultados.apply(classificar_tendencia, axis=1)
    
    print("\n4. Detectando tópicos emergentes...")
    
    df_resultados['emergente'] = df_resultados.apply(
        lambda row: row['variacao_percentual'] > 100 or (row['media_ultimos_3'] > 0 and row['primeiro'] == 0),
        axis=1
    )
    
    print("\n5. Ordenando por tendência...")
    df_resultados = df_resultados.sort_values('variacao_percentual', ascending=False)
    
    print("\n6. Salvando resultados...")
    
    caminho_saida.mkdir(parents=True, exist_ok=True)
    
    caminho_tendencias = caminho_saida / "tendencias.parquet"
    salvar_parquet(df_resultados, caminho_tendencias)
    print(f"   Tendências salvas em: {caminho_tendencias}")
    
    df_emergentes = df_resultados[df_resultados['emergente'] == True]
    if len(df_emergentes) > 0:
        caminho_emergentes = caminho_saida / "topicos_emergentes.parquet"
        salvar_parquet(df_emergentes, caminho_emergentes)
        print(f"   Tópicos emergentes: {len(df_emergentes)}")
        print(f"   Salvos em: {caminho_emergentes}")
    else:
        print("   Nenhum tópico emergente detectado")
    
    print("\n7. Gerando relatório...")
    
    relatorio = {
        "data_execucao": datetime.now().isoformat(),
        "periodo_inicio": data_min.isoformat(),
        "periodo_fim": data_max.isoformat(),
        "total_topicos": len(df_resultados),
        "topicos_emergentes": len(df_emergentes),
        "resumo_tendencias": {
            "alta_forte": int((df_resultados['classificacao'] == "Alta forte").sum()),
            "alta_moderada": int((df_resultados['classificacao'] == "Alta moderada").sum()),
            "estavel": int((df_resultados['classificacao'] == "Estável").sum()),
            "baixa_moderada": int((df_resultados['classificacao'] == "Baixa moderada").sum()),
            "baixa_forte": int((df_resultados['classificacao'] == "Baixa forte").sum())
        },
        "top_tendencias": df_resultados[['label', 'variacao_percentual', 'classificacao']].head(5).to_dict('records')
    }
    
    caminho_relatorio = caminho_saida / "relatorio_tendencias.json"
    with open(caminho_relatorio, 'w') as f:
        json.dump(relatorio, f, indent=2)
    print(f"   Relatório salvo em: {caminho_relatorio}")
    
    print("\n" + "=" * 60)
    print("ANÁLISE DE TENDÊNCIAS CONCLUÍDA!")
    print("=" * 60)
    
    print("\nResumo das tendências:")
    print(df_resultados[['label', 'variacao_percentual', 'classificacao', 'emergente']].to_string(index=False))
    
    return df_resultados, df_emergentes

def main():
    detectar_tendencias()

if __name__ == "__main__":
    main()
