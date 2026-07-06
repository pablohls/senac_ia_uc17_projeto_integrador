"""Gera um corpus de amostra para desenvolvimento/teste local (NÃO é dado real).

Cria `dados/raw/corpus.parquet` no schema A1 mínimo exigido pelo pipeline:
{doc_id, data, titulo, texto, fonte, categoria, url}. Útil quando o corpus
congelado ainda não foi materializado (a coleta real leva ~2h).

Uso: poetry run python scripts/gerar_amostra.py
"""

import pandas as pd

dados = {
    'doc_id': ['amostra01', 'amostra02', 'amostra03', 'amostra04', 'amostra05'],
    'data': ['2026-06-10', '2026-06-11', '2026-06-12', '2026-06-13', '2026-06-14'],
    'titulo': [
        'Novo imposto sobre compras internacionais',
        'Economia brasileira cresce em 2024',
        'Google lança nova inteligência artificial',
        'OMS alerta para nova variante',
        'Notícia curta',
    ],
    'texto': [
        'Governo anuncia novo imposto sobre compras internacionais a partir de agosto https://g1.globo.com',
        'Economia brasileira cresce 2.5% em 2024 segundo dados do IBGE divulgados hoje!!!',
        'Google lança nova inteligência artificial que promete revolucionar o mercado de tecnologia',
        'Saúde: OMS alerta para nova variante do vírus que preocupa autoridades mundiais',
        'Noticia muito curta e sem conteudo relevante',
    ],
    'fonte': ['amostra'] * 5,
    'categoria': ['economia', 'economia', 'tecnologia', 'saude', 'geral'],
    'url': [f'https://exemplo.com/artigo-{i}' for i in range(1, 6)],
}

df = pd.DataFrame(dados)
df.to_parquet('dados/raw/corpus.parquet', index=False)
print("Arquivo corpus.parquet (AMOSTRA) criado com sucesso!")
print(f"Total de notícias: {len(df)}")
