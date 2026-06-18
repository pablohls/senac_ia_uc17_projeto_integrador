import re
import pandas as pd

def limpar_texto(texto):
    if not texto or not isinstance(texto, str):
        return None
    
    # Remove URLs
    texto = re.sub(r'https?://\S+|www\.\S+', '', texto)
    
    # Remove HTML
    texto = re.sub(r'<[^>]+>', '', texto)
    
    # Remove caracteres de controle
    texto = re.sub(r'[\t\r]+', ' ', texto)
    
    # Remove emojis
    texto = re.sub(r'[^\w\s.,!?;:-]', '', texto, flags=re.UNICODE)
    
    # Remove pontuação repetida
    texto = re.sub(r'([!?])\1+', r'\1', texto)
    texto = re.sub(r'(\.)\1+', r'\1', texto)
    
    # Normaliza espaços
    texto = ' '.join(texto.split())
    
    # Converte para minúsculas
    texto = texto.lower()
    
    # Remove espaço antes de pontuação
    texto = re.sub(r'\s+([.,!?;:-])', r'\1', texto)
    
    # Filtra textos muito curtos
    if len(texto.strip()) < 10:
        return None
    
    return texto.strip()

def aplicar_limpeza_corpus(df):
    if 'texto' not in df.columns:
        raise ValueError("DataFrame precisa ter coluna 'texto'")
    
    if 'doc_id' not in df.columns:
        raise ValueError("DataFrame precisa ter coluna 'doc_id'")
    
    df = df.copy()
    df['texto_limpo'] = df['texto'].apply(limpar_texto)
    df_limpo = df.dropna(subset=['texto_limpo']).copy()
    
    # CORREÇÃO: mantém todas as colunas originais
    return df_limpo
