"""Templates de prompt do Analista IA (Story 5.2 — ADR-002 §Feature A).

Prompts fixos e versionáveis: mudá-los muda o produto, então moram aqui (e não
espalhados no código). Ambos são *grounded*: exigem que o LLM se baseie APENAS
nos títulos/trechos fornecidos — é a principal defesa contra invenção.
"""

from __future__ import annotations

# Rotulação: nome curto e legível para o assunto comum dos artigos.
PROMPT_ROTULACAO = """Você é um analista de tendências de um portal de notícias de tecnologia.

Baseando-se APENAS nos títulos e trechos de artigos abaixo, dê um nome curto
(máximo 8 palavras, em português) para o assunto comum a eles.

Responda SOMENTE com o nome do assunto — sem aspas, sem numeração, sem ponto final.

Artigos:
{contexto}"""

# "Por que sobe": parágrafo explicativo da ascensão do tópico.
PROMPT_WHY = """Você é um analista de tendências de um portal de notícias de tecnologia.

O assunto "{label}" está em ascensão nas notícias dos últimos dias.
Baseando-se APENAS nos títulos e trechos de artigos abaixo, explique em 2 a 4
frases (em português) por que este assunto está ganhando destaque agora.
Não invente fatos que não estejam nos artigos.

Responda SOMENTE com o parágrafo explicativo.

Artigos:
{contexto}"""


def montar_prompt_rotulacao(contexto: str) -> list[dict]:
    """Mensagens OpenAI-style para a rotulação de um tópico."""
    return [{"role": "user", "content": PROMPT_ROTULACAO.format(contexto=contexto)}]


def montar_prompt_why(label: str, contexto: str) -> list[dict]:
    """Mensagens OpenAI-style para o parágrafo "por que sobe" de um tópico."""
    return [{"role": "user", "content": PROMPT_WHY.format(label=label, contexto=contexto)}]
