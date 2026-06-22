"""
Módulo para visualização dos dados.
Gera gráficos e dashboards para análise.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from src.common.io import ler_parquet, salvar_parquet

def criar_graficos(caminho_serie=None, caminho_tendencias=None, 
                   caminho_topic_info=None, caminho_saida=None):
    """
    Gera gráficos a partir dos dados temporais.
    """
    
    if caminho_serie is None:
        caminho_serie = Path("dados/temporal/serie_temporal.parquet")
    
    if caminho_tendencias is None:
        caminho_tendencias = Path("dados/temporal/tendencias.parquet")
    
    if caminho_topic_info is None:
        caminho_topic_info = Path("dados/topics/topic_info.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/visualizacao")
    
    print("=" * 60)
    print("GERANDO VISUALIZAÇÕES")
    print("=" * 60)
    
    # Criar pasta de saída
    caminho_saida.mkdir(parents=True, exist_ok=True)
    
    # Configurar estilo
    plt.style.use('seaborn-v0_8-darkgrid')
    sns.set_palette("husl")
    
    # Passo 1: Carregar dados
    print("\n1. Carregando dados...")
    
    df_serie = ler_parquet(caminho_serie)
    df_serie['data'] = pd.to_datetime(df_serie['data'])
    print(f"   Série temporal: {len(df_serie)} registros")
    
    df_tendencias = ler_parquet(caminho_tendencias)
    print(f"   Tendências: {len(df_tendencias)} tópicos")
    
    df_topic_info = ler_parquet(caminho_topic_info)
    print(f"   Topic info: {len(df_topic_info)} tópicos")
    
    # Passo 2: Gráfico 1 - Série temporal por tópico
    print("\n2. Criando gráfico da série temporal...")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for topic_id in df_serie['topic_id'].unique():
        if topic_id == -1:
            continue
        df_topic = df_serie[df_serie['topic_id'] == topic_id]
        label = df_topic['label'].iloc[0]
        ax.plot(df_topic['data'], df_topic['count'], label=label, linewidth=2)
    
    ax.set_title('Série Temporal por Tópico', fontsize=14)
    ax.set_xlabel('Data', fontsize=12)
    ax.set_ylabel('Número de Notícias', fontsize=12)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    caminho_grafico1 = caminho_saida / "grafico_serie_temporal.png"
    plt.savefig(caminho_grafico1, dpi=150)
    print(f"   Salvo: {caminho_grafico1}")
    plt.close()
    
    # Passo 3: Gráfico 2 - Distribuição dos tópicos
    print("\n3. Criando gráfico de distribuição...")
    
    # Calcular total por tópico a partir da série
    totais = df_serie.groupby('topic_id')['count'].sum().reset_index()
    totais = totais.merge(df_topic_info[['topic_id', 'label']], on='topic_id')
    totais = totais.sort_values('count', ascending=False)
    
    # Remover outliers para o gráfico
    totais_plot = totais[totais['topic_id'] != -1]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(totais_plot['label'], totais_plot['count'], color=sns.color_palette("husl", len(totais_plot)))
    ax.set_title('Distribuição de Notícias por Tópico', fontsize=14)
    ax.set_xlabel('Tópico', fontsize=12)
    ax.set_ylabel('Total de Notícias', fontsize=12)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Adicionar valores nas barras
    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{int(height)}', ha='center', va='bottom')
    
    plt.tight_layout()
    caminho_grafico2 = caminho_saida / "grafico_distribuicao.png"
    plt.savefig(caminho_grafico2, dpi=150)
    print(f"   Salvo: {caminho_grafico2}")
    plt.close()
    
    # Passo 4: Gráfico 3 - Heatmap de frequência por dia
    print("\n4. Criando heatmap...")
    
    # Preparar dados para heatmap
    df_heat = df_serie[df_serie['topic_id'] != -1].pivot_table(
        index='data', 
        columns='topic_id', 
        values='count',
        fill_value=0
    )
    
    # Renomear colunas com labels
    labels = dict(zip(df_topic_info['topic_id'], df_topic_info['label']))
    df_heat = df_heat.rename(columns=labels)
    
    fig, ax = plt.subplots(figsize=(12, 6))
    im = ax.imshow(df_heat.T, aspect='auto', cmap='YlOrRd')
    
    ax.set_title('Heatmap de Frequência por Tópico', fontsize=14)
    ax.set_xlabel('Dias', fontsize=12)
    ax.set_ylabel('Tópico', fontsize=12)
    
    # Configurar eixos
    ax.set_xticks(range(len(df_heat.index)))
    ax.set_xticklabels(df_heat.index.strftime('%d/%m'), rotation=45, ha='right')
    ax.set_yticks(range(len(df_heat.columns)))
    ax.set_yticklabels(df_heat.columns)
    
    plt.colorbar(im, ax=ax, label='Número de Notícias')
    plt.tight_layout()
    caminho_grafico3 = caminho_saida / "grafico_heatmap.png"
    plt.savefig(caminho_grafico3, dpi=150)
    print(f"   Salvo: {caminho_grafico3}")
    plt.close()
    
    # Passo 5: Gráfico 4 - Tendências (variação percentual)
    print("\n5. Criando gráfico de tendências...")
    
    # Remover outliers
    df_tend_plot = df_tendencias[df_tendencias['topic_id'] != -1].copy()
    df_tend_plot = df_tend_plot.sort_values('variacao_percentual', ascending=False)
    
    # Definir cores
    cores = ['green' if v >= 0 else 'red' for v in df_tend_plot['variacao_percentual']]
    
    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(df_tend_plot['label'], df_tend_plot['variacao_percentual'], color=cores)
    
    ax.set_title('Variação Percentual por Tópico', fontsize=14)
    ax.set_xlabel('Tópico', fontsize=12)
    ax.set_ylabel('Variação (%)', fontsize=12)
    ax.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax.grid(True, alpha=0.3, axis='y')
    
    # Adicionar valores
    for bar in bars:
        height = bar.get_height()
        va = 'bottom' if height >= 0 else 'top'
        ax.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va=va)
    
    plt.tight_layout()
    caminho_grafico4 = caminho_saida / "grafico_tendencias.png"
    plt.savefig(caminho_grafico4, dpi=150)
    print(f"   Salvo: {caminho_grafico4}")
    plt.close()
    
    # Passo 6: Gráfico 5 - Média móvel
    print("\n6. Criando gráfico de média móvel...")
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for topic_id in df_serie['topic_id'].unique():
        if topic_id == -1:
            continue
        df_topic = df_serie[df_serie['topic_id'] == topic_id]
        label = df_topic['label'].iloc[0]
        
        # Plotar contagem diária (mais claro)
        ax.plot(df_topic['data'], df_topic['count'], 
                label=f'{label} (diário)', linewidth=1, alpha=0.5)
        
        # Plotar média móvel (mais escuro)
        ax.plot(df_topic['data'], df_topic['media_movel_7d'], 
                label=f'{label} (média 7d)', linewidth=2)
    
    ax.set_title('Média Móvel de 7 dias por Tópico', fontsize=14)
    ax.set_xlabel('Data', fontsize=12)
    ax.set_ylabel('Número de Notícias', fontsize=12)
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    caminho_grafico5 = caminho_saida / "grafico_media_movel.png"
    plt.savefig(caminho_grafico5, dpi=150)
    print(f"   Salvo: {caminho_grafico5}")
    plt.close()
    
    # Passo 7: Salvar relatório de visualização
    print("\n7. Gerando relatório...")
    
    relatorio = {
        "data_execucao": datetime.now().isoformat(),
        "graficos_gerados": [
            "grafico_serie_temporal.png",
            "grafico_distribuicao.png",
            "grafico_heatmap.png",
            "grafico_tendencias.png",
            "grafico_media_movel.png"
        ],
        "total_topicos": len(df_topic_info),
        "total_documentos": int(df_serie['count'].sum())
    }
    
    caminho_relatorio = caminho_saida / "relatorio_visualizacao.json"
    with open(caminho_relatorio, 'w') as f:
        json.dump(relatorio, f, indent=2)
    print(f"   Relatório salvo em: {caminho_relatorio}")
    
    print("\n" + "=" * 60)
    print("VISUALIZAÇÕES GERADAS COM SUCESSO!")
    print("=" * 60)
    
    print("\nArquivos gerados:")
    for arquivo in caminho_saida.glob("*.png"):
        print(f"   - {arquivo.name}")
    
    return caminho_saida

def criar_dashboard(caminho_graficos=None, caminho_saida=None):
    """
    Cria um dashboard HTML com os gráficos.
    """
    
    if caminho_graficos is None:
        caminho_graficos = Path("dados/visualizacao")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/visualizacao")
    
    print("\n8. Criando dashboard HTML...")
    
    # Criar HTML
    html = f'''<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - TrendRadar</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .card {{
            background-color: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
            padding: 15px;
        }}
        .card h3 {{
            margin-top: 0;
            color: #555;
            text-align: center;
        }}
        .card img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #888;
            font-size: 14px;
        }}
        @media (max-width: 900px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <h1>📊 Dashboard - Análise de Tópicos</h1>
    <div class="grid">
        <div class="card">
            <h3>Série Temporal por Tópico</h3>
            <img src="grafico_serie_temporal.png" alt="Série Temporal">
        </div>
        <div class="card">
            <h3>Distribuição por Tópico</h3>
            <img src="grafico_distribuicao.png" alt="Distribuição">
        </div>
        <div class="card">
            <h3>Heatmap de Frequência</h3>
            <img src="grafico_heatmap.png" alt="Heatmap">
        </div>
        <div class="card">
            <h3>Variação Percentual</h3>
            <img src="grafico_tendencias.png" alt="Tendências">
        </div>
        <div class="card">
            <h3>Média Móvel (7 dias)</h3>
            <img src="grafico_media_movel.png" alt="Média Móvel">
        </div>
    </div>
    <div class="footer">
        TrendRadar - Análise de Tópicos | Gerado em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
</body>
</html>'''
    
    caminho_html = caminho_saida / "dashboard.html"
    with open(caminho_html, 'w') as f:
        f.write(html)
    print(f"   Dashboard salvo em: {caminho_html}")
    
    return caminho_html

def main():
    caminho_graficos = criar_graficos()
    criar_dashboard(caminho_graficos)
    print("\nPara visualizar o dashboard, abra no navegador:")
    print(f"   file://{caminho_graficos}/dashboard.html")

if __name__ == "__main__":
    main()