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

"""
Configurações do projeto TrendRadar baseadas em Pydantic.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import yaml
from pydantic import BaseModel, Field

class SitemapConfig(BaseModel):
    index_url: str
    meses: int
    categorias: List[str] = []
    user_agent: str
    rate_limit_s: float

class ExtractConfig(BaseModel):
    user_agent: str
    rate_limit_s: float
    timeout_s: int
    limite: Optional[int] = None

class CanaltechConfig(BaseModel):
    index_url: str
    meses: int
    user_agent: str
    rate_limit_s: float

class ColetaConfig(BaseModel):
    sitemap: SitemapConfig
    extract: ExtractConfig
    canaltech: CanaltechConfig

class TrendScoreParams(BaseModel):
    w: int = 7
    alpha: float = 1.0
    H: int = 60
    lambda_burst: float = 1.0
    n_min: int = 5
    k: float = 2.5
    epsilon: float = Field(default=1e-6, alias="eps")

    class Config:
        populate_by_name = True

class Config(BaseModel):
    fontes: List[str]
    coleta: ColetaConfig
    embedding_model: str
    trend_score: TrendScoreParams

def load_config(path: str | Path = "config/config.yaml") -> Config:
    """Carrega a configuração do arquivo YAML e valida com Pydantic."""
    caminho = Path(path)
    if not caminho.exists():
        caminho = Path(__file__).parents[2] / "config" / "config.yaml"
    
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f)
        if "trend_score" in dados and "eps" in dados["trend_score"]:
            dados["trend_score"]["epsilon"] = dados["trend_score"].pop("eps")
            
        return Config(**dados)