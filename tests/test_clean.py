"""
Testes para a função de limpeza de texto.
"""

import pytest
from src.pln.clean import limpar_texto, aplicar_limpeza_corpus
import pandas as pd

class TestLimpezaTexto:
    def test_remove_urls(self):
        resultado = limpar_texto("Noticia https://link.com continua")
        assert resultado == "noticia continua"
    
    def test_remove_html(self):
        resultado = limpar_texto("<p>Texto importante</p>")
        assert resultado == "texto importante"
    
    def test_remove_emojis(self):
        resultado = limpar_texto("Olá 😀 Tudo bem")
        assert resultado == "olá tudo bem"
    
    def test_normaliza_espacos(self):
        resultado = limpar_texto("Um    texto    com   muitos espaços")
        assert resultado == "um texto com muitos espaços"
        assert "  " not in resultado
    
    def test_idempotencia(self):
        texto_sujo = "Ola!!!  Mundo  https://link.com"
        primeira = limpar_texto(texto_sujo)
        segunda = limpar_texto(primeira)
        assert primeira == segunda
    
    def test_nao_remove_acentos(self):
        resultado = limpar_texto("Ações da educação básica")
        assert "ações" in resultado
        assert "educação" in resultado
        assert "básica" in resultado
    
    def test_texto_curto(self):
        assert limpar_texto("Oi") is None
        assert limpar_texto("") is None
    
    def test_texto_none(self):
        assert limpar_texto(None) is None
    
    def test_mantem_numeros(self):
        resultado = limpar_texto("Preço subiu 5% em 2024")
        assert "5" in resultado
        assert "2024" in resultado

    def test_limiar_configuravel(self):
        texto = "Um texto de tamanho médio para o teste"
        # limiar alto descarta; limiar baixo mantém (AC3 — min configurável)
        assert limpar_texto(texto, min_chars=100) is None
        assert limpar_texto(texto, min_chars=5) is not None

class TestAplicarLimpezaCorpus:
    def test_preserva_colunas(self):
        df = pd.DataFrame({
            'doc_id': [1, 2],
            'texto': ['Texto longo com link https://link.com', 'Outro texto qualquer'],
            'data': ['2024-01-01', '2024-01-02'],
            'fonte': ['G1', 'G2']
        })
        
        resultado = aplicar_limpeza_corpus(df)
        
        assert 'doc_id' in resultado.columns
        assert 'texto_limpo' in resultado.columns
        assert 'data' in resultado.columns
        assert 'fonte' in resultado.columns
        assert len(resultado) == 2
    
    def test_filtra_textos_curtos(self):
        df = pd.DataFrame({
            'doc_id': [1, 2],
            'texto': ['Texto longo e interessante', 'Oi']
        })
        
        resultado = aplicar_limpeza_corpus(df)
        assert len(resultado) == 1
        assert resultado.iloc[0]['doc_id'] == 1