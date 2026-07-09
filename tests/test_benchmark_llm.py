"""Testes do harness de benchmark A/B/C (Story 5.6 — protocolo-empirico.md §9).

Cobrem o que é automatizável: a montagem determinística da amostra
estratificada e o embaralhamento cego reprodutível por seed. A QUALIDADE das
saídas é avaliação humana (rubrica 1–5) — fora do escopo de unit-test, por
desenho da story.
"""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

# `scripts/` não é pacote: carrega o módulo direto do arquivo.
_SPEC = importlib.util.spec_from_file_location(
    "benchmark_llm", Path(__file__).resolve().parents[1] / "scripts" / "benchmark_llm.py"
)
bench = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bench)


# --------------------------------------------------------------------------
# Amostra estratificada (AC2)
# --------------------------------------------------------------------------
@pytest.fixture
def artefatos_sinteticos():
    """Scores/topic_info mínimos cobrindo todos os estratos do protocolo §3."""
    ids = [0, 5, 12, 20, 21, 22, 23, 24, 25, 26, 35, 90, 91, 92]
    scores = pd.DataFrame(
        {
            "topic_id": ids,
            # 35 = anomalia; 20-26 = topo; 90-92 = baixo suporte; 0/5/12 fixos.
            "trend_score": [3.0, 1.0, 1.0, 9, 8, 7, 6, 5, 4, 3.5, 8.5, -1, -1, -1],
            "support_ok": [True] * 11 + [False] * 3,
            "is_anomaly": [tid == 35 for tid in ids],
        }
    )
    topic_info = pd.DataFrame(
        {
            "topic_id": ids,
            "label": [f"label {tid}" for tid in ids],
            "size": [300, 90, 60, 30, 30, 30, 30, 30, 30, 30, 40, 10, 12, 11],
        }
    )
    return scores, topic_info


def test_montar_amostra_estratos(artefatos_sinteticos):
    """12 tópicos, sem repetição, com todos os estratos do protocolo."""
    scores, topic_info = artefatos_sinteticos
    amostra = bench.montar_amostra(scores, topic_info)

    topicos = amostra["topicos"]
    ids = [t["topic_id"] for t in topicos]
    estratos = {t["topic_id"]: t["estrato"] for t in topicos}

    assert len(topicos) == 12
    assert len(set(ids)) == 12, "tópico repetido entre estratos"
    assert sum(1 for t in topicos if t["estrato"] == "topo") == bench.ESTRATO_TOPO_N
    assert estratos[35] == "anomalia"
    assert estratos[5] == "ruidoso" and estratos[12] == "ruidoso"
    assert estratos[0] == "multi_tema"
    # Nicho: os 2 MENORES sizes com support_ok=False (90 e 92, não o 91).
    assert {t for t, e in estratos.items() if e == "nicho"} == {90, 92}
    # Topo exclui os reservados (0, 5, 12, 35) mesmo com trend_score alto.
    assert 35 not in [t for t, e in estratos.items() if e == "topo"]


def test_montar_amostra_deterministica(artefatos_sinteticos):
    """Mesmos artefatos ⇒ mesma amostra (congelável)."""
    scores, topic_info = artefatos_sinteticos
    assert bench.montar_amostra(scores, topic_info) == bench.montar_amostra(
        scores, topic_info
    )


def test_amostra_perguntas_rag():
    """8 perguntas fixas: 5 respondíveis + 3 pegadinhas (protocolo §3)."""
    assert len(bench.PERGUNTAS_RAG) == 8
    assert sum(1 for p in bench.PERGUNTAS_RAG if p["respondivel"]) == 5
    assert sum(1 for p in bench.PERGUNTAS_RAG if not p["respondivel"]) == 3


# --------------------------------------------------------------------------
# Embaralhamento cego (AC4)
# --------------------------------------------------------------------------
@pytest.fixture
def brutos_sinteticos():
    """Saídas de 3 modelos × {2 tópicos T1 + 1 pergunta T3} + 1 falha."""
    linhas = []
    for modelo in ["modelo-a", "modelo-b", "modelo-c"]:
        for tarefa, item in [("T1", "t1"), ("T1", "t2"), ("T3", "q1")]:
            linhas.append(
                {
                    "modelo": modelo,
                    "tarefa": tarefa,
                    "item_id": item,
                    "item_ref": f"ref {item}",
                    "prompt": f"prompt {item}",
                    "saida": f"saida de {modelo} para {tarefa}/{item}",
                    "status": "ok",
                }
            )
    linhas.append(
        {
            "modelo": "modelo-a", "tarefa": "T2", "item_id": "t9", "item_ref": "r",
            "prompt": "p", "saida": "", "status": "falha_llm",
        }
    )
    return pd.DataFrame(linhas)


def test_embaralhar_cego_deterministico(brutos_sinteticos):
    """Mesma seed ⇒ mesma planilha e mesmo mapa (reprodutível)."""
    planilha1, mapa1 = bench.embaralhar_cego(brutos_sinteticos, seed=42)
    planilha2, mapa2 = bench.embaralhar_cego(brutos_sinteticos, seed=42)
    assert mapa1 == mapa2
    pd.testing.assert_frame_equal(planilha1, planilha2)


def test_embaralhar_cego_nao_revela_modelo(brutos_sinteticos):
    """A planilha não tem coluna de modelo; o vínculo mora só no mapa (AC4)."""
    planilha, mapa = bench.embaralhar_cego(brutos_sinteticos, seed=42)
    assert "modelo" not in planilha.columns
    assert set(planilha["opcao"].unique()) == {"opcao_1", "opcao_2", "opcao_3"}
    # Rubrica presente e vazia, pronta para o avaliador.
    for criterio in bench.CRITERIOS_RUBRICA:
        assert planilha[f"nota_{criterio}"].isna().all()


def test_embaralhar_cego_mapa_reconstroi(brutos_sinteticos):
    """Mapa + planilha reconstroem exatamente as saídas por modelo (round-trip)."""
    planilha, mapa = bench.embaralhar_cego(brutos_sinteticos, seed=7)
    for linha in planilha.itertuples(index=False):
        modelo = mapa[f"{linha.tarefa}|{linha.item_id}|{linha.opcao}"]
        assert linha.saida == f"saida de {modelo} para {linha.tarefa}/{linha.item_id}"


def test_embaralhar_cego_descarta_falhas(brutos_sinteticos):
    """Linhas com falha do LLM não vão para avaliação humana."""
    planilha, _ = bench.embaralhar_cego(brutos_sinteticos, seed=42)
    assert "t9" not in planilha["item_id"].values


# --------------------------------------------------------------------------
# Medição e regra de decisão (AC1/AC5)
# --------------------------------------------------------------------------
def test_medir_chamada_stream_ok(monkeypatch):
    """Stream com conteúdo ⇒ status ok, tokens contados, latências medidas."""
    monkeypatch.setattr(bench, "chat_stream", lambda *a, **k: iter(["Olá", " ", "mundo"]))
    medida = bench.medir_chamada([{"role": "user", "content": "oi"}], temperature=0.0)
    assert medida["status"] == "ok"
    assert medida["saida"] == "Olá mundo"
    assert medida["tokens_aprox"] == 3
    assert medida["latencia_1o_token_s"] is not None
    assert medida["latencia_total_s"] >= medida["latencia_1o_token_s"]


def test_medir_chamada_stream_vazio(monkeypatch):
    """Stream vazio (LLM fora, contrato do 5.1) ⇒ falha_llm sem exceção."""
    monkeypatch.setattr(bench, "chat_stream", lambda *a, **k: iter([]))
    medida = bench.medir_chamada([{"role": "user", "content": "oi"}], temperature=0.0)
    assert medida["status"] == "falha_llm"
    assert medida["saida"] == ""
    assert medida["latencia_1o_token_s"] is None


def _desempenho(modelos_latencias: dict[str, float]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"modelo": m, "tarefa": "T1", "latencia_total_s": lat}
         for m, lat in modelos_latencias.items()]
    )


def test_decidir_fidelidade_eliminatoria():
    """Fidelidade média < 3 descarta o modelo mesmo com nota alta (§7.3)."""
    qualidade = pd.DataFrame(
        {"fidelidade": [2.5, 4.0], "qualidade_ponderada": [4.8, 4.0]},
        index=["alucinador", "fiel"],
    )
    vencedor, justificativa = bench.decidir(qualidade, _desempenho({"alucinador": 1, "fiel": 9}))
    assert vencedor == "fiel"
    assert "alucinador" in justificativa


def test_decidir_empate_por_latencia():
    """Δ qualidade ≤ 0,3 ⇒ empate técnico ⇒ menor latência vence (§7.2)."""
    qualidade = pd.DataFrame(
        {"fidelidade": [4.5, 4.5], "qualidade_ponderada": [4.2, 4.0]},
        index=["lento", "rapido"],
    )
    vencedor, justificativa = bench.decidir(qualidade, _desempenho({"lento": 30.0, "rapido": 8.0}))
    assert vencedor == "rapido"
    assert "empate" in justificativa
