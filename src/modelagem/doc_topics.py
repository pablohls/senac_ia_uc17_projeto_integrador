import pandas as pd
from pathlib import Path
from datetime import datetime
import json

from src.common.io import ler_parquet, salvar_parquet

def criar_doc_topics(caminho_doc_topics=None, caminho_corpus=None, 
                      caminho_topic_info=None, caminho_saida=None):
    
    if caminho_doc_topics is None:
        caminho_doc_topics = Path("dados/processed/doc_topics.parquet")
    
    if caminho_corpus is None:
        caminho_corpus = Path("dados/processed/corpus_clean.parquet")
    
    if caminho_topic_info is None:
        caminho_topic_info = Path("dados/processed/topic_info.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/topics")
    
    print("=" * 60)
    print("CRIANDO TABELA DOC_TOPICS")
    print("=" * 60)
    
    print("\n1. Carregando dados...")
    
    df_doc_topics = ler_parquet(caminho_doc_topics)
    print(f"   Doc topics: {len(df_doc_topics)} linhas")
    
    df_corpus = ler_parquet(caminho_corpus)
    print(f"   Corpus: {len(df_corpus)} linhas")
    
    df_topic_info = ler_parquet(caminho_topic_info)
    print(f"   Topic info: {len(df_topic_info)} topicos")
    
    print("\n2. Adicionando datas aos documentos...")
    
    df_resultado = df_doc_topics.merge(
        df_corpus[['doc_id', 'data']], 
        on='doc_id', 
        how='left'
    )
    
    print(f"   Resultado: {len(df_resultado)} linhas")
    
    sem_data = df_resultado['data'].isna().sum()
    if sem_data > 0:
        print(f"   Aviso: {sem_data} documentos sem data")
        df_resultado['data'] = df_resultado['data'].fillna(pd.Timestamp.now())
    
    print("\n3. Validando consistencia com topic_info...")
    
    topicos_validos = set(df_topic_info['Topic'].values)
    topicos_presentes = set(df_resultado['topic_id'].values)
    
    topicos_invalidos = topicos_presentes - topicos_validos
    if topicos_invalidos:
        print(f"   Aviso: topicos invalidos: {topicos_invalidos}")
    else:
        print(f"   OK: Todos os topicos sao validos")
    
    print("\n4. Salvando resultado...")
    
    caminho_saida.mkdir(parents=True, exist_ok=True)
    caminho_final = caminho_saida / "doc_topics.parquet"
    salvar_parquet(df_resultado, caminho_final)
    print(f"   Salvo em: {caminho_final}")
    
    print("\n5. Validando contagens...")
    
    total_docs = len(df_resultado)
    contagem_por_topico = df_resultado['topic_id'].value_counts().sort_index()
    
    print(f"   Total de documentos: {total_docs}")
    print("\n   Contagem por topico:")
    for topico, contagem in contagem_por_topico.items():
        nome = "Outliers" if topico == -1 else f"Topico {topico}"
        print(f"      {nome}: {contagem} documentos")
    
    soma_contagens = contagem_por_topico.sum()
    print(f"\n   Soma das contagens: {soma_contagens}")
    
    if soma_contagens == total_docs:
        print("   VALIDACAO OK: Contagens conferem com o total")
    else:
        print(f"   ERRO: Soma ({soma_contagens}) nao confere com total ({total_docs})")
    
    print("\n6. Salvando relatorio de validacao...")
    
    relatorio = {
        "data_execucao": datetime.now().isoformat(),
        "total_documentos": total_docs,
        "topicos_validos": len(topicos_validos),
        "contagem_por_topico": contagem_por_topico.to_dict(),
        "topicos_invalidos": list(topicos_invalidos) if topicos_invalidos else [],
        "validacao_ok": str(soma_contagens == total_docs)
    }
    
    caminho_relatorio = caminho_saida / "doc_topics_validacao.json"
    with open(caminho_relatorio, 'w') as f:
        json.dump(relatorio, f, indent=2)
    print(f"   Relatorio salvo em: {caminho_relatorio}")
    
    print("\n" + "=" * 60)
    print("DOC_TOPICS CRIADO COM SUCESSO!")
    print("=" * 60)
    
    return df_resultado

def main():
    criar_doc_topics()

if __name__ == "__main__":
    main()