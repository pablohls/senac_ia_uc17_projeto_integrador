"""Cliente LLM provider-agnostic do TrendRadar (Fase 5 — ADR-002, Story 5.1).

Uma única função — :func:`chat` — fala com qualquer endpoint OpenAI-compatible
(Ollama local no demo, endpoint remoto no dev), com `base_url` e `model` vindos
da seção `insight:` do `config/config.yaml`. O resto do projeto não sabe (nem
se importa) onde o modelo roda: trocar o provedor é trocar uma linha de config.

Contrato de degradação graciosa (inegociável — ADR-002):
    qualquer falha (timeout, conexão recusada, erro do servidor, resposta
    malformada) faz `chat()` retornar ``None`` com log de aviso — NUNCA propaga
    exceção. É isso que permite ao dashboard seguir com labels c-TF-IDF quando
    o LLM está fora, no mesmo espírito da Camada 2 (LSTM) da Fase 3.

Segurança: a chave do endpoint vem da env var apontada por `insight.api_key_env`
(default `LLM_API_KEY`). Sem a var definida, usa o dummy "ollama" — o Ollama
exige *algum* valor mas o ignora. Nunca hardcodear segredo.
"""

from __future__ import annotations

import logging
import os

from openai import OpenAI

from src.common.config import config

logger = logging.getLogger(__name__)

# Chave fictícia aceita pelo Ollama (que não valida chave). Endpoints reais
# leem a chave da env var `insight.api_key_env` — nunca deste arquivo.
_API_KEY_DUMMY = "ollama"


def _criar_cliente() -> OpenAI:
    """Instancia o cliente OpenAI-compatible a partir da config `insight`."""
    ins = config.insight
    api_key = os.environ.get(ins.api_key_env) or _API_KEY_DUMMY
    return OpenAI(
        base_url=ins.base_url,
        api_key=api_key,
        timeout=ins.timeout_s,
        # Sem retry automático: falha rápida e o chamador segue sem LLM
        # (degradação graciosa); retries triplicariam a espera no pior caso.
        max_retries=0,
    )


def chat(
    messages: list[dict],
    *,
    temperature: float,
    max_tokens: int,
) -> str | None:
    """Envia `messages` ao LLM configurado e retorna o texto da resposta.

    Args:
        messages: lista OpenAI-style, ex.: ``[{"role": "user", "content": "..."}]``.
        temperature: use ``config.insight.temperature_batch`` (Analista IA)
            ou ``config.insight.temperature_chat`` (RAG).
        max_tokens: limite de tokens da resposta (ver ``config.insight.max_tokens``).

    Returns:
        Texto da resposta, ou ``None`` em qualquer falha (best-effort — AC2).
    """
    try:
        cliente = _criar_cliente()
        resposta = cliente.chat.completions.create(
            model=config.insight.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        conteudo = resposta.choices[0].message.content
        if not conteudo:
            logger.warning("LLM devolveu resposta vazia/malformada — seguindo sem LLM.")
            return None
        return conteudo
    except Exception as exc:  # noqa: BLE001 — degradação graciosa é o contrato (AC2)
        logger.warning(
            "LLM indisponível em %s (%s: %s) — seguindo sem LLM (degradação graciosa).",
            config.insight.base_url,
            type(exc).__name__,
            exc,
        )
        return None
