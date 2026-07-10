"""Motor de resposta do RAG — resposta com citação de fontes (Story 5.5, ADR-002 §B).

Fecha o ciclo: pergunta → retriever (5.4) → prompt RESTRITIVO → `chat()` (5.1)
→ resposta + citações clicáveis. O prompt é o coração anti-alucinação da story:
o LLM só pode usar os trechos recuperados e deve ADMITIR quando eles não
respondem (validado com perguntas-pegadinha no gate).

Degradação graciosa (AC5):
  - retriever vazio  ⇒ recusa honesta (``MSG_SEM_BASE``), sem chamar o LLM;
  - `chat()` → None  ⇒ mensagem amigável (``MSG_INDISPONIVEL``), sem quebrar.
"""

from __future__ import annotations

import logging

import pandas as pd

from src.common.config import config
from src.common.llm import chat, chat_stream
from src.rag.retriever import retrieve

logger = logging.getLogger(__name__)

CORPUS_PATH = "dados/raw/corpus.parquet"

# Mensagens fixas dos caminhos de degradação (AC3/AC5) — os testes e a UI
# dependem do texto exato; mudar aqui é mudar o produto.
MSG_SEM_BASE = "Não encontrei essa informação nos artigos coletados."
MSG_INDISPONIVEL = (
    "Assistente indisponível no momento (LLM local fora do ar) — "
    "o restante do dashboard segue funcionando."
)

# Prompt restritivo (AC1/AC3): responder SÓ com os trechos; admitir ausência.
PROMPT_RAG = """Você é o assistente do SONAR e responde perguntas sobre \
notícias de tecnologia em PT-BR.

Responda à pergunta usando SOMENTE as informações dos trechos de artigos abaixo.
Se ALGUM trecho for relacionado ao tema da pergunta, responda resumindo o que ele
traz e cite-o — mesmo que a cobertura seja parcial. Use a resposta exata
"{msg_sem_base}" (sozinha, SEM colchetes nem citações) apenas quando NENHUM trecho
tiver qualquer relação com a pergunta.
Não invente fatos nem use conhecimento externo. Seja conciso (até 5 frases) e
indique entre colchetes o número dos trechos que sustentam cada afirmação, ex.: [1].

Trechos:
{trechos}

Pergunta: {pergunta}"""

# Cache do texto dos artigos (doc_id → texto) — carregado uma vez por processo.
_textos_cache: pd.Series | None = None


def _obter_textos() -> pd.Series:
    """Série `doc_id → texto` do corpus A1, em cache de módulo."""
    global _textos_cache
    if _textos_cache is None:
        corpus = pd.read_parquet(CORPUS_PATH, columns=["doc_id", "texto"])
        _textos_cache = corpus.set_index("doc_id")["texto"]
    return _textos_cache


def montar_prompt_rag(pergunta: str, resultados: list[dict]) -> list[dict]:
    """Mensagens OpenAI-style com os trechos numerados injetados (AC1)."""
    textos = _obter_textos()
    blocos = []
    for i, r in enumerate(resultados, start=1):
        trecho = str(textos.get(r["doc_id"], ""))[: config.insight.trecho_max_chars]
        blocos.append(f"[{i}] {r['titulo']} ({r['fonte']})\n{trecho}")
    conteudo = PROMPT_RAG.format(
        msg_sem_base=MSG_SEM_BASE, trechos="\n\n".join(blocos), pergunta=pergunta
    )
    return [{"role": "user", "content": conteudo}]


def _citacoes(resultados: list[dict]) -> list[dict]:
    """Metadados de citação clicável (AC2) na ordem dos trechos do prompt."""
    return [
        {"titulo": r["titulo"], "url": r["url"], "fonte": r["fonte"]}
        for r in resultados
    ]


def responder(pergunta: str) -> dict:
    """Responde à pergunta com base no corpus, citando as fontes (AC1/AC2/AC5).

    Returns:
        ``{"resposta": str, "citacoes": list[dict], "status": str}`` com status
        em ``{"ok", "sem_base", "llm_indisponivel"}``. Nunca levanta exceção.
    """
    resultados = retrieve(pergunta)
    if not resultados:
        logger.info("RAG sem base para a pergunta — recusa honesta.")
        return {"resposta": MSG_SEM_BASE, "citacoes": [], "status": "sem_base"}

    resposta = chat(
        montar_prompt_rag(pergunta, resultados),
        temperature=config.insight.temperature_chat,
        max_tokens=config.insight.max_tokens,
    )
    if resposta is None:
        return {"resposta": MSG_INDISPONIVEL, "citacoes": [], "status": "llm_indisponivel"}

    return {"resposta": resposta.strip(), "citacoes": _citacoes(resultados), "status": "ok"}


def responder_stream(pergunta: str) -> dict:
    """Variante streaming para o painel de chat (AC4).

    Returns:
        ``{"tokens": Iterator[str] | None, "resposta_pronta": str | None,
        "citacoes": list[dict]}`` — sem base ⇒ ``tokens=None`` e a recusa em
        ``resposta_pronta``; com base ⇒ gerador de tokens (stream vazio =
        LLM indisponível; o chamador exibe ``MSG_INDISPONIVEL``).
    """
    resultados = retrieve(pergunta)
    if not resultados:
        return {"tokens": None, "resposta_pronta": MSG_SEM_BASE, "citacoes": []}

    tokens = chat_stream(
        montar_prompt_rag(pergunta, resultados),
        temperature=config.insight.temperature_chat,
        max_tokens=config.insight.max_tokens,
    )
    return {"tokens": tokens, "resposta_pronta": None, "citacoes": _citacoes(resultados)}
