"""
Configurações do projeto TrendRadar
"""

class Config:
    # Modelo de embeddings para português
    embedding_model = "paraphrase-multilingual-mpnet-base-v2"
    
    # Tamanho do lote para processamento em GPU
    batch_size = 64
    
    # Pastas dos dados
    dados_raw = "dados/raw"
    dados_processed = "dados/processed"
