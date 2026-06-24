"""
Módulo para atribuição de tópicos por documento.
Cria a tabela final doc_topics.parquet com doc_id, data e topic_id.
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import json

from src.common.io import ler_parquet, salvar_parquet

def criar_doc_topics(caminho_doc_topics=None, caminho_corpus=None, 
                      caminho_topic_info=None, caminho_saida=None):
    """
    Cria a tabela doc_topics.parquet com doc_id, data e topic_id.
    
    Passos:
    1. Carregar doc_topics do clustering (topic_id por documento)
    2. Carregar corpus limpo (datas dos documentos)
    3. Fazer join por doc_id para adicionar a data
    4. Validar consistência com topic_info
    5. Salvar resultado final
    """
    
    # Definir caminhos padrão
    if caminho_doc_topics is None:
        caminho_doc_topics = Path("dados/topics/doc_topics.parquet")
    
    if caminho_corpus is None:
        caminho_corpus = Path("dados/processed/corpus_clean.parquet")
    
    if caminho_topic_info is None:
        caminho_topic_info = Path("dados/topics/topic_info.parquet")
    
    if caminho_saida is None:
        caminho_saida = Path("dados/topics")
    
    print("=" * 60)
    print("CRIANDO TABELA DOC_TOPICS")
    print("=" * 60)
    
    # Passo 1: Carregar dados
    print("\n1. Carregando dados...")
    
    df_doc_topics = ler_parquet(caminho_doc_topics)
    print(f"   Doc topics: {len(df_doc_topics)} linhas")
    
    df_corpus = ler_parquet(caminho_corpus)
    print(f"   Corpus: {len(df_corpus)} linhas")
    
    df_topic_info = ler_parquet(caminho_topic_info)
    print(f"   Topic info: {len(df_topic_info)} tópicos")
    
    # Passo 2: Juntar doc_topics com corpus para adicionar a data
    print("\n2. Adicionando datas aos documentos...")
    
    df_resultado = df_doc_topics.merge(
        df_corpus[['doc_id', 'data']], 
        on='doc_id', 
        how='left'
    )
    
    print(f"   Resultado: {len(df_resultado)} linhas")
    
    # CORREÇÃO F12: Fail-fast se houver datas faltando
    sem_data = df_resultado['data'].isna().sum()
    if sem_data > 0:
        docs_sem_data = df_resultado[df_resultado['data'].isna()]['doc_id'].tolist()
        raise ValueError(
            f"{sem_data} documentos sem data: {docs_sem_data[:10]}... "
            "Verifique o join com corpus_clean"
        )
    
    # Passo 3: Validar consistência com topic_info
    print("\n3. Validando consistência com topic_info...")
    
    topicos_validos = set(df_topic_info['topic_id'].values)
    topicos_presentes = set(df_resultado['topic_id'].values)
    
    topicos_invalidos = topicos_presentes - topicos_validos
    if topicos_invalidos:
        print(f"   Aviso: tópicos inválidos: {topicos_invalidos}")
    else:
        print(f"   OK: Todos os tópicos são válidos")
    
    # Passo 4: Salvar resultado
    print("\n4. Salvando resultado...")
    
    caminho_saida.mkdir(parents=True, exist_ok=True)
    caminho_final = caminho_saida / "doc_topics_final.parquet"
    salvar_parquet(df_resultado, caminho_final)
    print(f"   Salvo em: {caminho_final}")
    
    # Passo 5: Validar contagens
    print("\n5. Validando contagens...")
    
    total_docs = len(df_resultado)
    contagem_por_topico = df_resultado['topic_id'].value_counts().sort_index()
    
    print(f"   Total de documentos: {total_docs}")
    print("\n   Contagem por tópico:")
    for topico, contagem in contagem_por_topico.items():
        nome = "Outliers" if topico == -1 else f"Tópico {topico}"
        print(f"      {nome}: {contagem} documentos")
    
    soma_contagens = contagem_por_topico.sum()
    print(f"\n   Soma das contagens: {soma_contagens}")
    
    if soma_contagens == total_docs:
        print("   VALIDAÇÃO OK: Contagens conferem com o total")
    else:
        print(f"   ERRO: Soma ({soma_contagens}) não confere com total ({total_docs})")
    
    # Passo 6: Salvar relatório de validação
    print("\n6. Salvando relatório de validação...")
    
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
    print(f"   Relatório salvo em: {caminho_relatorio}")
    
    print("\n" + "=" * 60)
    print("DOC_TOPICS CRIADO COM SUCESSO!")
    print("=" * 60)
    
    return df_resultado

def main():
    """Ponto de entrada do script."""
    criar_doc_topics()

if __name__ == "__main__":
    main()