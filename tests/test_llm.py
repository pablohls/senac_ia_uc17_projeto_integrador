"""
Testes do cliente LLM provider-agnostic (Story 5.1 — ver ADR-002).

O contrato central é a degradação graciosa: sucesso devolve texto; QUALQUER
falha (conexão recusada, timeout, resposta malformada) devolve None sem
propagar exceção. Os testes mockam o cliente `openai` — nada de rede no CI.
O smoke test contra o Ollama real é opcional e pula quando o endpoint não existe.
"""

import socket
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.common.config import Config, InsightParams, load_config
from src.common.llm import chat

MENSAGENS = [{"role": "user", "content": "diga olá"}]


def _resposta_mock(texto: str | None):
    """Monta o objeto de resposta no formato do SDK openai."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=texto))]
    )


def _ollama_no_ar(host: str = "localhost", port: int = 11434) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


class TestChatSucesso:
    def test_sucesso_devolve_texto(self):
        """Caminho feliz: resposta do endpoint vira str (AC1)."""
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock("olá!")
        with patch("src.common.llm.OpenAI", return_value=cliente):
            resultado = chat(MENSAGENS, temperature=0.0, max_tokens=20)
        assert resultado == "olá!"

    def test_parametros_da_config_sao_usados(self):
        """base_url/model/timeout vêm da config — zero número mágico (AC3)."""
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock("ok")
        with patch("src.common.llm.OpenAI", return_value=cliente) as ctor:
            chat(MENSAGENS, temperature=0.3, max_tokens=64)
        from src.common.config import config

        assert ctor.call_args.kwargs["base_url"] == config.insight.base_url
        assert ctor.call_args.kwargs["timeout"] == config.insight.timeout_s
        create_kwargs = cliente.chat.completions.create.call_args.kwargs
        assert create_kwargs["model"] == config.insight.model
        assert create_kwargs["temperature"] == 0.3
        assert create_kwargs["max_tokens"] == 64


class TestChatDegradacaoGraciosa:
    def test_conexao_recusada_devolve_none(self):
        """Endpoint fora do ar → None, sem exceção (AC2 — inegociável)."""
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = ConnectionError(
            "[Errno 111] Connection refused"
        )
        with patch("src.common.llm.OpenAI", return_value=cliente):
            assert chat(MENSAGENS, temperature=0.0, max_tokens=20) is None

    def test_timeout_devolve_none(self):
        """Timeout do servidor → None, sem exceção (AC2)."""
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = TimeoutError("read timed out")
        with patch("src.common.llm.OpenAI", return_value=cliente):
            assert chat(MENSAGENS, temperature=0.0, max_tokens=20) is None

    def test_falha_ao_criar_cliente_devolve_none(self):
        """Erro já na construção do cliente também não propaga (AC2)."""
        with patch("src.common.llm.OpenAI", side_effect=RuntimeError("boom")):
            assert chat(MENSAGENS, temperature=0.0, max_tokens=20) is None

    def test_resposta_vazia_devolve_none(self):
        """Resposta malformada (content vazio/None) → None (AC2)."""
        cliente = MagicMock()
        cliente.chat.completions.create.return_value = _resposta_mock(None)
        with patch("src.common.llm.OpenAI", return_value=cliente):
            assert chat(MENSAGENS, temperature=0.0, max_tokens=20) is None

    def test_falha_emite_log_de_aviso(self, caplog):
        """A falha silenciosa não é muda: registra warning (AC2)."""
        cliente = MagicMock()
        cliente.chat.completions.create.side_effect = ConnectionError("refused")
        with patch("src.common.llm.OpenAI", return_value=cliente):
            with caplog.at_level("WARNING", logger="src.common.llm"):
                chat(MENSAGENS, temperature=0.0, max_tokens=20)
        assert any("degradação graciosa" in m for m in caplog.messages)


class TestInsightParams:
    def test_defaults_do_adr_002(self):
        """Defaults firmados no ADR-002 §Parâmetros (+ timeout_s do should-fix @po)."""
        p = InsightParams()
        assert p.base_url == "http://localhost:11434/v1"
        assert p.model == "qwen2.5:14b"
        assert p.temperature_batch == 0.0
        assert p.temperature_chat == 0.3
        assert p.max_tokens == 512
        assert p.timeout_s > 60  # precisa acomodar o cold start do Ollama (~60s)
        assert p.rag_top_k == 6
        assert p.top_artigos == 5

    def test_validacao_rejeita_valores_invalidos(self):
        with pytest.raises(Exception):
            InsightParams(max_tokens=0)
        with pytest.raises(Exception):
            InsightParams(timeout_s=-1)

    def test_config_yaml_carrega_secao_insight(self):
        """A seção insight: do config.yaml valida e integra ao Config raiz (AC3)."""
        cfg = load_config()
        assert isinstance(cfg, Config)
        assert isinstance(cfg.insight, InsightParams)
        assert cfg.insight.base_url.endswith("/v1")
        assert cfg.dados_insight == "dados/insight"


@pytest.mark.skipif(not _ollama_no_ar(), reason="Ollama não está no ar (smoke opcional)")
class TestSmokeOllama:
    """Prova provider-agnostic contra o endpoint local real (AC4).

    A MESMA função `chat()` que os mocks exercitam responde aqui contra o
    Ollama (`insight.base_url`); apontar para outro endpoint OpenAI-compatible
    é trocar só base_url/model no config.yaml. Pula no CI (sem Ollama).
    """

    def test_chat_contra_ollama_local(self):
        resultado = chat(
            [{"role": "user", "content": "Responda apenas: pong"}],
            temperature=0.0,
            max_tokens=10,
        )
        assert isinstance(resultado, str) and len(resultado) > 0
