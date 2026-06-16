import pandas as pd

dados = {
    'doc_id': [1, 2, 3, 4, 5],
    'texto': [
        'Governo anuncia novo imposto sobre compras internacionais a partir de agosto https://g1.globo.com',
        'Economia brasileira cresce 2.5% em 2024 segundo dados do IBGE divulgados hoje!!!',
        'Google lança nova inteligência artificial que promete revolucionar o mercado de tecnologia',
        'Saúde: OMS alerta para nova variante do vírus que preocupa autoridades mundiais',
        'Noticia muito curta e sem conteudo relevante'
    ]
}

df = pd.DataFrame(dados)
df.to_parquet('dados/raw/corpus.parquet', index=False)
print("Arquivo corpus.parquet criado com sucesso!")
print(f"Total de notícias: {len(df)}")