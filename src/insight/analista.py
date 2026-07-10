"""Analista IA — montagem de contexto e geração de briefings (Story 5.2, ADR-002 §A).

Para cada tópico em ascensão, seleciona os artigos mais representativos
(`doc_topics × corpus` por `probabilidade`), monta o contexto (título + trecho)
e pede ao LLM um rótulo curto (`label_llm`) e um parágrafo "por que sobe"
(`why_summary`). Grounding: os prompts exigem base APENAS nos artigos dados.

Origem do trecho (should-fix @po): coluna `texto` do corpus A1
(`dados/raw/corpus.parquet`) — o texto original legível, não o `corpus_clean`
normalizado para embeddings, que remove pontuação/maiúsculas e prejudicaria a
leitura do LLM. Truncado em `config.insight.trecho_max_chars`.

Degradação graciosa (AC5): `chat()` devolvendo `None` para um tópico vira
fallback (mantém o `label` c-TF-IDF, `why_summary` vazio) com log — nunca
exceção. Se o primeiro tópico falhar nas duas chamadas, assume-se LLM fora do
ar e os demais tópicos recebem fallback direto (evita esperar N timeouts).
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from src.common.config import config
from src.common.llm import chat
from src.insight.prompts import montar_prompt_rotulacao, montar_prompt_why

logger = logging.getLogger(__name__)

# Nº máximo de palavras do label (AC2) — contrato da story, não parâmetro tunável.
MAX_PALAVRAS_LABEL = 8

# Caracteres aceitos num label: latino (com acentos PT), dígitos e pontuação
# comum. O LLM quantizado às vezes emite tokens de outro alfabeto (cirílico) ou
# concatena palavras — nesses casos o label cai no fallback c-TF-IDF.
_LABEL_LATINO = re.compile(r"^[\sA-Za-z0-9À-ÿ.,&/()\-'ªº°²³+:]*$")
_MAX_TOKEN_LEN = 20  # palavra maior que isso = concatenação/lixo (ex.: "FonesBluetoothPromoção")


def _label_suspeito(label: str) -> bool:
    """True se o label do LLM parece corrompido (alfabeto estranho ou concatenado)."""
    if not label.strip():
        return True
    if not _LABEL_LATINO.match(label):  # cirílico, emoji, etc.
        return True
    return any(len(w) > _MAX_TOKEN_LEN for w in label.split())


def selecionar_topicos_ascensao(scores: pd.DataFrame, topic_info: pd.DataFrame) -> pd.DataFrame:
    """Filtra os tópicos em ascensão e anexa o label c-TF-IDF (fallback).

    Critério (AC1): `topic_id != -1` (descarta outliers) e `support_ok == True`,
    ordenados por `trend_score` decrescente.
    """
    ascensao = scores[(scores["topic_id"] != -1) & (scores["support_ok"])].copy()
    ascensao = ascensao.sort_values("trend_score", ascending=False)
    return ascensao.merge(topic_info[["topic_id", "label"]], on="topic_id", how="left")


def montar_contexto(
    topic_id: int, doc_topics: pd.DataFrame, corpus: pd.DataFrame
) -> str:
    """Monta o bloco de contexto (título + trecho) dos artigos mais representativos.

    Seleciona os `config.insight.top_artigos` documentos do tópico com maior
    `probabilidade` (doc_topics) e junta com o corpus A1 por `doc_id`.
    """
    docs = doc_topics[doc_topics["topic_id"] == topic_id]
    docs = docs.sort_values("probabilidade", ascending=False).head(config.insight.top_artigos)
    artigos = docs.merge(corpus[["doc_id", "titulo", "texto"]], on="doc_id", how="inner")

    blocos: list[str] = []
    for i, row in enumerate(artigos.itertuples(index=False), start=1):
        trecho = str(row.texto)[: config.insight.trecho_max_chars]
        blocos.append(f"{i}. {row.titulo}\n   {trecho}")
    return "\n\n".join(blocos)


def limpar_label(bruto: str) -> str:
    """Normaliza o label do LLM: sem aspas/quebras, no máximo 8 palavras (AC2)."""
    label = bruto.strip().splitlines()[0].strip().strip("\"'").strip()
    palavras = label.split()
    if len(palavras) > MAX_PALAVRAS_LABEL:
        label = " ".join(palavras[:MAX_PALAVRAS_LABEL])
    return label


def gerar_briefing(label_ctfidf: str, contexto: str) -> tuple[str, str, bool]:
    """Gera (label_llm, why_summary) para um tópico via LLM.

    Returns:
        Tupla ``(label, why, llm_ok)``. Em falha do LLM (AC5), devolve o
        fallback ``(label_ctfidf, "", False)`` — quem chama decide logar/contar.
    """
    ins = config.insight

    bruto = chat(
        montar_prompt_rotulacao(contexto),
        temperature=ins.temperature_batch,
        max_tokens=ins.max_tokens,
    )
    if bruto is None:
        return label_ctfidf, "", False
    label = limpar_label(bruto)
    if _label_suspeito(label):
        logger.warning("Label do LLM suspeito (%r) — usando fallback c-TF-IDF %r",
                       label, label_ctfidf)
        label = label_ctfidf

    why = chat(
        montar_prompt_why(label, contexto),
        temperature=ins.temperature_batch,
        max_tokens=ins.max_tokens,
    )
    if why is None:
        # Rotulou mas não explicou: mantém o label gerado, why vazio.
        return label, "", False
    return label, why.strip(), True
