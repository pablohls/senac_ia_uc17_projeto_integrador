"""Carregamento e validação da configuração central do TrendRadar.

Toda a pipeline lê seus parâmetros a partir de `config/config.yaml` através de
um objeto pydantic — nunca de constantes espalhadas no código (Coding Standards).

Seções:
  - coleta (Fase 1: sitemap, extract, canaltech)
  - limpeza / embedding / clustering (Fase 2: PLN e modelagem de tópicos)
  - trend_score (Fase 3: ADR-001)
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

# Caminho padrão do arquivo de configuração (relativo à raiz do projeto).
DEFAULT_CONFIG_PATH = Path("config/config.yaml")


# --------------------------------------------------------------------------
# Fase 3 — Trend Score (ver docs/architecture/adr-001-trend-score.md)
# --------------------------------------------------------------------------
class TrendScoreParams(BaseModel):
    """Parâmetros do algoritmo Trend Score (ver ADR-001)."""

    w: int = Field(7, gt=0, description="Janela (dias) da média móvel.")
    alpha: float = Field(1.0, ge=0, description="Suavização de Laplace.")
    H: int = Field(60, gt=0, description="Horizonte (dias) de base histórica.")
    lambda_burst: float = Field(1.0, ge=0, description="Peso do termo de surto.")
    n_min: int = Field(5, gt=0, description="Mínimo de docs por tópico no ranking.")
    k: float = Field(2.5, gt=0, description="Desvios-padrão p/ anomalia.")

    # Camada 2 — LSTM (Story 3.3). Sem número mágico no código.
    sigma_min: float = Field(
        1.0, gt=0,
        description="Piso do σ dos resíduos na surpresa — séries quase constantes "
                    "têm σ≈0 e explodiriam o z (falso positivo com flutuação de <1 doc).",
    )
    seed: int = Field(42, description="Seed do torch/numpy (reprodutibilidade).")
    lstm_hidden_size: int = Field(32, gt=0, description="Neurônios da camada oculta.")
    lstm_epochs: int = Field(50, gt=0, description="Épocas de treino por tópico.")
    lstm_lr: float = Field(0.01, gt=0, description="Learning rate do Adam.")


# --------------------------------------------------------------------------
# Fase 1 — Coleta (Stories 1.2, 1.3, 1.4)
# --------------------------------------------------------------------------
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


# --------------------------------------------------------------------------
# Fase 2 — PLN e modelagem de tópicos (Stories 2.1–2.4)
# --------------------------------------------------------------------------
class LimpezaParams(BaseModel):
    """Parâmetros da limpeza/normalização (Story 2.1)."""

    min_text_length: int = Field(
        10, gt=0, description="Descarta textos com menos caracteres que isso após limpeza."
    )


class EmbeddingParams(BaseModel):
    """Parâmetros da geração de embeddings (Story 2.2)."""

    model_name: str | None = Field(
        None,
        description="Modelo Sentence-Transformers; se None, herda `embedding_model` raiz.",
    )
    batch_size: int = Field(64, gt=0, description="Tamanho do lote no encode.")


class ClusteringParams(BaseModel):
    """Parâmetros do clustering BERTopic/UMAP/HDBSCAN (Story 2.3)."""

    min_topic_size: int = Field(2, gt=0, description="Tamanho mínimo p/ formar tópico.")
    n_neighbors: int = Field(15, gt=0, description="Vizinhos do UMAP.")
    n_components: int = Field(5, gt=0, description="Dimensões de saída do UMAP.")
    min_cluster_size: int = Field(2, gt=0, description="Tamanho mínimo do cluster (HDBSCAN).")
    cluster_selection_epsilon: float = Field(0.1, ge=0, description="Epsilon do HDBSCAN.")
    random_state: int = Field(42, description="Seed do UMAP (reprodutibilidade).")
    label_top_n: int = Field(3, gt=0, description="Nº de termos no label automático.")


# --------------------------------------------------------------------------
# Raiz
# --------------------------------------------------------------------------
class Config(BaseModel):
    """Configuração raiz do projeto, espelhando `config/config.yaml`."""

    fontes: list[str] = Field(..., min_length=1)
    embedding_model: str
    trend_score: TrendScoreParams = Field(default_factory=TrendScoreParams)
    coleta: ColetaParams
    limpeza: LimpezaParams = Field(default_factory=LimpezaParams)
    embedding: EmbeddingParams = Field(default_factory=EmbeddingParams)
    clustering: ClusteringParams = Field(default_factory=ClusteringParams)

    # Diretórios dos artefatos (contratos A1–A4).
    dados_raw: str = "dados/raw"
    dados_processed: str = "dados/processed"
    dados_topics: str = "dados/topics"
    dados_scores: str = "dados/scores"

    @model_validator(mode="after")
    def _herdar_embedding_model(self) -> "Config":
        """`embedding.model_name` herda o `embedding_model` raiz se não definido."""
        if self.embedding.model_name is None:
            self.embedding.model_name = self.embedding_model
        return self


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
        # Fallback: resolve relativo à raiz do repositório (independente do cwd).
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Arquivo de configuração não encontrado: {config_path}")
    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Config(**data)


# Instância compartilhada para módulos que fazem `from src.common.config import config`.
config = load_config()
