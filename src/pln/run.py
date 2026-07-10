import sys
from pathlib import Path
import time
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.common.io import ler_parquet, salvar_parquet, atualizar_manifest
from src.common.config import config
from src.pln.clean import aplicar_limpeza_corpus
from src.pln.embed import embed_corpus
from src.modelagem.topics import modelar_topicos
from src.modelagem.doc_topics import criar_doc_topics

def _excluir_catalogo(df_raw):
    """Remove da análise os docs cujas URLs são catálogo/spec (config-driven).

    Ex.: `/produto/` do Canaltech — páginas de especificação de aparelhos, não
    notícias. Ficam no corpus bruto (A1), mas fora da modelagem (tópicos/RAG).
    Sem padrões configurados, devolve o corpus intacto.
    """
    padroes = config.corpus_analise.excluir_url_contendo
    if not padroes or "url" not in df_raw.columns:
        return df_raw
    padrao = "|".join(p.replace(".", r"\.") for p in padroes)
    catalogo = df_raw["url"].str.contains(padrao, case=False, na=False, regex=True)
    if catalogo.any():
        print(f"Excluídos da análise (catálogo {padroes}): {int(catalogo.sum())} docs")
    return df_raw[~catalogo].copy()


def executar_limpeza():
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

    df_raw = _excluir_catalogo(df_raw)

    df_clean = aplicar_limpeza_corpus(df_raw)
    print(f"Mantidos {len(df_clean)} artigos")
    
    caminho_saida.parent.mkdir(parents=True, exist_ok=True)
    salvar_parquet(df_clean, caminho_saida)
    print(f"Salvo em {caminho_saida}")

    # Manifesto transversal de reprodutibilidade (F9 — contrato A1)
    atualizar_manifest(
        "limpeza",
        n_docs=len(df_clean),
        stage_version="2.1",
        params={"limpeza": config.limpeza.model_dump()},
    )

    return True

def executar_embeddings():
    print("\n" + "=" * 60)
    print("ETAPA 2: GERAÇÃO DE EMBEDDINGS")
    print("=" * 60)
    embed_corpus()
    return True

def executar_clustering():
    print("\n" + "=" * 60)
    print("ETAPA 3: CLUSTERING E TÓPICOS")
    print("=" * 60)
    modelar_topicos()
    return True

def executar_doc_topics():
    print("\n" + "=" * 60)
    print("ETAPA 4: ATRIBUIÇÃO DE TÓPICOS")
    print("=" * 60)
    criar_doc_topics()
    return True

def main():
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
                sys.exit(1)
        except SystemExit:
            raise
        except Exception as e:
            print(f"\nERRO na etapa {nome}: {e}")
            sys.exit(1)
    
    fim_total = time.time()
    
    print("\n" + "=" * 60)
    print("PIPELINE DA FASE 2 CONCLUÍDA COM SUCESSO!")
    print(f"Tempo total: {fim_total - inicio_total:.2f} segundos")
    print("=" * 60)

if __name__ == "__main__":
    main()
