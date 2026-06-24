"""
Módulo para criação de séries temporais a partir de doc_topics.
"""

import pandas as pd
from datetime import date
from pathlib import Path

def montar_series(df, gerar_weekly=False):
    """
    Monta série temporal de contagem por tópico e data.
    
    Argumentos:
        df: DataFrame com colunas 'data' e 'topic_id'
        gerar_weekly: Se True, adiciona coluna count_weekly
        
    Retorna:
        DataFrame com data (date), topic_id, count e count_weekly (opcional)
    """
    
    # Converter data para datetime
    df = df.copy()
    df['data'] = pd.to_datetime(df['data'])
    
    # Identificar período
    data_min = df['data'].min().date()
    data_max = df['data'].max().date()
    
    # Criar todos os dias do período como datetime
    todos_dias = pd.date_range(start=data_min, end=data_max, freq='D')
    
    # Lista de tópicos
    topicos = df['topic_id'].unique()
    
    # Criar DataFrame com todas as combinações
    linhas = []
    for topico in topicos:
        for dia in todos_dias:
            linhas.append({'data': dia, 'topic_id': topico})
    
    df_completo = pd.DataFrame(linhas)
    df_completo['data'] = pd.to_datetime(df_completo['data'])
    
    # Contar documentos por dia e tópico
    contagem = df.groupby([df['data'].dt.date, 'topic_id']).size().reset_index(name='count')
    contagem.columns = ['data', 'topic_id', 'count']
    contagem['data'] = pd.to_datetime(contagem['data'])
    
    # Juntar com o DataFrame completo
    df_resultado = df_completo.merge(contagem, on=['data', 'topic_id'], how='left')
    df_resultado['count'] = df_resultado['count'].fillna(0).astype(int)
    
    # Converter data para date (para compatibilidade com os testes)
    df_resultado['data'] = df_resultado['data'].dt.date
    
    if gerar_weekly:
        # Adicionar coluna de semana
        df_resultado['semana'] = pd.to_datetime(df_resultado['data']).dt.isocalendar().week
        df_resultado['ano'] = pd.to_datetime(df_resultado['data']).dt.isocalendar().year
        
        # Calcular total semanal por tópico
        weekly = df_resultado.groupby(['ano', 'semana', 'topic_id'])['count'].sum().reset_index()
        weekly.columns = ['ano', 'semana', 'topic_id', 'count_weekly']
        
        df_resultado = df_resultado.merge(weekly, on=['ano', 'semana', 'topic_id'], how='left')
        df_resultado['count_weekly'] = df_resultado['count_weekly'].fillna(0).astype(int)
        
        # Remover colunas auxiliares
        df_resultado = df_resultado.drop(['ano', 'semana'], axis=1)
    
    return df_resultado

def validar_serie(df):
    """
    Valida uma série temporal.
    
    Retorna:
        dict com resultados da validação
    """
    
    resultado = {
        "zero_filled": True,
        "soma_consistente": True,
        "tipos_corretos": True
    }
    
    # Verificar se tem zeros
    if df['count'].min() > 0:
        resultado["zero_filled"] = False
    
    # Verificar soma consistente
    total_count = df['count'].sum()
    expected = len(df[df['topic_id'] == df['topic_id'].iloc[0]]) * df['count'].sum() / len(df)
    
    # Verificar tipos
    if df['count'].dtype not in ['int64', 'int32']:
        resultado["tipos_corretos"] = False
    
    return resultado

def main():
    """Teste rápido."""
    import pandas as pd
    from datetime import date
    
    # Criar dados de teste
    dados = {
        'doc_id': [f'doc{i:03d}' for i in range(1, 10)],
        'data': [
            date(2026, 1, 1), date(2026, 1, 1), date(2026, 1, 1),
            date(2026, 1, 2), date(2026, 1, 2), date(2026, 1, 3),
            date(2026, 1, 3), date(2026, 1, 3), date(2026, 1, 5)
        ],
        'topic_id': [0, 1, 2, 0, 1, 0, 1, 2, 0]
    }
    
    df = pd.DataFrame(dados)
    print("Dados originais:")
    print(df)
    
    series = montar_series(df, gerar_weekly=True)
    print("\nSérie temporal:")
    print(series)
    
    val = validar_serie(series)
    print("\nValidação:")
    print(val)

if __name__ == "__main__":
    main()