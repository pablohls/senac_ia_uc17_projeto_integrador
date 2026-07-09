"""
Testes do responder RAG (Story 5.5 — ver ADR-002 §Feature B, §Riscos).

`retrieve()` e `chat()`/`chat_stream()` sempre mockados (sem rede, sem modelo).
Cobrem: injeção dos trechos no prompt restritivo, citações, recusa honesta sem
base, mensagem amigável com LLM fora, e temperatura da config.
"""

from unittest.mock import patch

import pandas as pd
import pytest

import src.rag.responder as responder_mod
from src.rag.responder import (
    MSG_INDISPONIVEL,
    MSG_SEM_BASE,
    montar_prompt_rag,
    responder,
    responder_stream,
)

RESULTADOS = [
    {"doc_id": "d1", "titulo": "Apple sobe preços", "url": "u1",
     "fonte": "olhar_digital", "score": 0.9},
    {"doc_id": "d2", "titulo": "iPhone em promoção", "url": "u2",
     "fonte": "canaltech", "score": 0.8},
]


@pytest.fixture(autouse=True)
def _textos_dublados(monkeypatch):
    """Corpus dublado: doc_id → texto, sem tocar o disco."""
    textos = pd.Series(
        {"d1": "A Apple anunciou aumento de preços por causa dos chips. " * 20,
         "d2": "O iPhone 16 apareceu em promoção nas lojas."},
    )
    monkeypatch.setattr(responder_mod, "_textos_cache", textos)
    yield
    monkeypatch.setattr(responder_mod, "_textos_cache", None)


class TestPromptRestritivo:
    def test_injeta_trechos_numerados_e_instrucao(self):
        """AC1/AC3: prompt contém os trechos, os títulos e a instrução restritiva."""
        msgs = montar_prompt_rag("por que o iPhone subiu?", RESULTADOS)
        conteudo = msgs[0]["content"]
        assert "SOMENTE" in conteudo
        assert MSG_SEM_BASE in conteudo  # instrução de recusa honesta
        assert "[1] Apple sobe preços" in conteudo
        assert "[2] iPhone em promoção" in conteudo
        assert "aumento de preços por causa dos chips" in conteudo
        assert "por que o iPhone subiu?" in conteudo

    def test_trecho_respeita_trecho_max_chars(self):
        from src.common.config import config

        msgs = montar_prompt_rag("pergunta", RESULTADOS[:1])
        bloco = msgs[0]["content"].split("[1]")[1]
        # o texto de d1 tem ~1140 chars; o bloco carrega no máx. o truncado + metadados
        assert len(bloco) < config.insight.trecho_max_chars + 200


class TestResponder:
    def test_ok_devolve_resposta_com_citacoes(self):
        """AC1/AC2: resposta do LLM + citações clicáveis na ordem dos trechos."""
        with patch.object(responder_mod, "retrieve", return_value=RESULTADOS):
            with patch.object(responder_mod, "chat", return_value="Por causa dos chips [1]."):
                res = responder("por que o iPhone subiu?")
        assert res["status"] == "ok"
        assert res["resposta"] == "Por causa dos chips [1]."
        assert [c["titulo"] for c in res["citacoes"]] == ["Apple sobe preços", "iPhone em promoção"]
        assert res["citacoes"][0]["url"] == "u1"

    def test_sem_base_recusa_honesta_sem_chamar_llm(self):
        """AC3/AC5: retriever vazio → MSG_SEM_BASE e o LLM nem é chamado."""
        with patch.object(responder_mod, "retrieve", return_value=[]):
            with patch.object(responder_mod, "chat") as chat_mock:
                res = responder("qual o placar do jogo de ontem?")
        assert res == {"resposta": MSG_SEM_BASE, "citacoes": [], "status": "sem_base"}
        chat_mock.assert_not_called()

    def test_llm_fora_mensagem_amigavel(self):
        """AC5: chat() → None ⇒ MSG_INDISPONIVEL, sem exceção."""
        with patch.object(responder_mod, "retrieve", return_value=RESULTADOS):
            with patch.object(responder_mod, "chat", return_value=None):
                res = responder("pergunta")
        assert res["status"] == "llm_indisponivel"
        assert res["resposta"] == MSG_INDISPONIVEL
        assert res["citacoes"] == []

    def test_usa_temperature_chat_da_config(self):
        """AC1: temperature = config.insight.temperature_chat (não a batch)."""
        from src.common.config import config

        with patch.object(responder_mod, "retrieve", return_value=RESULTADOS):
            with patch.object(responder_mod, "chat", return_value="ok") as chat_mock:
                responder("pergunta")
        assert chat_mock.call_args.kwargs["temperature"] == config.insight.temperature_chat


class TestResponderStream:
    def test_sem_base_devolve_resposta_pronta(self):
        with patch.object(responder_mod, "retrieve", return_value=[]):
            res = responder_stream("pergunta fora do corpus")
        assert res["tokens"] is None
        assert res["resposta_pronta"] == MSG_SEM_BASE
        assert res["citacoes"] == []

    def test_com_base_devolve_gerador_e_citacoes(self):
        def _tokens(*a, **k):
            yield from ["Por ", "causa ", "dos chips."]

        with patch.object(responder_mod, "retrieve", return_value=RESULTADOS):
            with patch.object(responder_mod, "chat_stream", side_effect=_tokens):
                res = responder_stream("pergunta")
        assert res["resposta_pronta"] is None
        assert "".join(res["tokens"]) == "Por causa dos chips."
        assert len(res["citacoes"]) == 2
