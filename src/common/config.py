"""
Configurações do projeto TrendRadar
"""

import yaml
from pathlib import Path
from pydantic import BaseModel, Field

class EmbeddingConfig(BaseModel):
    model_name: str = "paraphrase-multilingual-mpnet-base-v2"
    batch_size: int = 64

class ClusteringConfig(BaseModel):
    min_topic_size: int = 2
    n_neighbors: int = 15
    min_cluster_size: int = 2
    cluster_selection_epsilon: float = 0.1
    random_state: int = 42

class LimpezaConfig(BaseModel):
    min_text_length: int = 10

class Config(BaseModel):
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    clustering: ClusteringConfig = Field(default_factory=ClusteringConfig)
    limpeza: LimpezaConfig = Field(default_factory=LimpezaConfig)
    dados_raw: str = "dados/raw"
    dados_processed: str = "dados/processed"
    dados_topics: str = "dados/topics"

def carregar_config(caminho=None):
    if caminho is None:
        caminho = Path("config/config.yaml")
    
    if not caminho.exists():
        return Config()
    
    with open(caminho) as f:
        dados = yaml.safe_load(f)
    
    return Config(**dados)

# Instância global
config = carregar_config()

# Para compatibilidade com código antigo
Config = Config