"""Limpeza e normalização de texto PT-BR (Story 2.1).

Remove ruído (URLs, HTML, emojis), normaliza espaços/caixa e descarta textos
curtos demais. O limiar vem de `config.limpeza.min_text_length` — nenhum
número mágico no código (Coding Standards).
"""

import re

from src.common.config import config


def limpar_texto(texto, min_chars=None):
    """Limpa e normaliza um texto; retorna None se inválido ou curto demais."""
    if min_chars is None:
        min_chars = config.limpeza.min_text_length

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

    # Filtra textos muito curtos (limiar da config — Story 2.1 AC3)
    if len(texto.strip()) < min_chars:
        return None

    return texto.strip()


def aplicar_limpeza_corpus(df, min_chars=None):
    """Aplica a limpeza ao corpus, preservando todas as colunas originais."""
    if 'texto' not in df.columns:
        raise ValueError("DataFrame precisa ter coluna 'texto'")

    if 'doc_id' not in df.columns:
        raise ValueError("DataFrame precisa ter coluna 'doc_id'")

    df = df.copy()
    df['texto_limpo'] = df['texto'].apply(lambda t: limpar_texto(t, min_chars=min_chars))
    df_limpo = df.dropna(subset=['texto_limpo']).copy()

    # Mantém todas as colunas originais (schema A1 + texto_limpo)
    return df_limpo
