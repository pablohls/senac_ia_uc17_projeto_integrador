"""Carregamento e validação da configuração central do TrendRadar.

Toda a pipeline lê seus parâmetros a partir de `config/config.yaml` através de
um objeto pydantic — nunca de constantes espalhadas no código (Coding Standards).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

# Caminho padrão do arquivo de configuração (relativo à raiz do projeto).
DEFAULT_CONFIG_PATH = Path("config/config.yaml")


class TrendScoreParams(BaseModel):
    """Parâmetros do algoritmo Trend Score (ver ADR-001)."""

    w: int = Field(7, gt=0, description="Janela (dias) da média móvel.")
    alpha: float = Field(1.0, ge=0, description="Suavização de Laplace.")
    H: int = Field(60, gt=0, description="Horizonte (dias) de base histórica.")
    lambda_burst: float = Field(1.0, ge=0, description="Peso do termo de surto.")
    n_min: int = Field(5, gt=0, description="Mínimo de docs por tópico no ranking.")
    k: float = Field(2.5, gt=0, description="Desvios-padrão p/ anomalia.")


class SitemapParams(BaseModel):
    """Parâmetros do coletor de sitemap (Story 1.2)."""

    index_url: str = Field(..., description="Sitemap index do portal.")
    meses: int = Field(4, gt=0, description="Janela histórica em meses (inclui o corrente).")
    categorias: list[str] = Field(
        default_factory=list, description="Filtro opcional por categoria (vazio = todas)."
    )
    user_agent: str = Field(
        "TrendRadar/0.1 (projeto integrador IA; coleta academica)",
        description="Identificação enviada ao servidor (NFR4).",
    )
    rate_limit_s: float = Field(1.0, ge=0, description="Pausa entre requisições, em segundos.")


class ExtractParams(BaseModel):
    """Parâmetros da extração de texto (Story 1.3 — dataset congelado A1)."""

    user_agent: str = Field(
        "TrendRadar/0.1 (projeto integrador IA; coleta academica)",
        description="Identificação enviada ao servidor (NFR4).",
    )
    rate_limit_s: float = Field(1.0, ge=0, description="Pausa entre downloads, em segundos.")
    timeout_s: int = Field(30, gt=0, description="Tempo máximo por requisição, em segundos.")
    limite: int | None = Field(
        None, description="Máximo de artigos a extrair (amostra/teste); None = todos."
    )


class CanaltechParams(BaseModel):
    """Parâmetros da segunda fonte Canaltech (Story 1.4)."""

    index_url: str = Field(..., description="Sitemap index do Canaltech.")
    meses: int = Field(4, gt=0, description="Janela histórica em meses (filtra por lastmod).")
    user_agent: str = Field(
        "TrendRadar/0.1 (projeto integrador IA; coleta academica)",
        description="Identificação enviada ao servidor (NFR4).",
    )
    rate_limit_s: float = Field(1.0, ge=0, description="Pausa entre requisições, em segundos.")


class ColetaParams(BaseModel):
    """Bloco de configuração da fase de coleta."""

    sitemap: SitemapParams
    extract: ExtractParams = Field(default_factory=ExtractParams)
    canaltech: CanaltechParams | None = None


class Config(BaseModel):
    """Configuração raiz do projeto, espelhando `config/config.yaml`."""

    fontes: list[str] = Field(..., min_length=1)
    embedding_model: str
    trend_score: TrendScoreParams
    coleta: ColetaParams


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> Config:
    """Lê e valida `config.yaml`, retornando um objeto `Config`.

    Args:
        path: caminho do YAML de configuração.

    Returns:
        Instância validada de :class:`Config`.

    Raises:
        FileNotFoundError: se o arquivo não existir.
        pydantic.ValidationError: se algum campo estiver ausente/inválido.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config(**data)
