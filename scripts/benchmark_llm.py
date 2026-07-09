"""Harness de benchmark A/B/C dos LLMs locais (Story 5.6 — protocolo-empirico.md).

Mede a shortlist do ADR-002 (Qwen2.5-14B × Qwen3.5-9B × Gemma 3-12B) sobre a
MESMA amostra congelada e os MESMOS prompts de produção, variando só o modelo —
o resultado justifica (ou troca) o `insight.model` do config com dado cego.

Reúso (IDS — REUSE > CREATE): todas as chamadas passam por `src/common/llm.py`
(Story 5.1), trocando apenas `config.insight.model` em runtime; o contexto dos
tópicos vem de `src/insight/analista.py` (5.2) e o prompt RAG de
`src/rag/responder.py` (5.5) — nenhum cliente ou prompt novo é criado aqui.

Subcomandos (pipeline do protocolo §6):
    poetry run python scripts/benchmark_llm.py amostra      # 1. congela a amostra
    poetry run python scripts/benchmark_llm.py executar     # 2. roda os 3 modelos
    poetry run python scripts/benchmark_llm.py planilha     # 3. planilha cega
    poetry run python scripts/benchmark_llm.py consolidar   # 5. relatório final

Degradação graciosa (AC6): modelo ausente no endpoint é PULADO com log (o
benchmark segue com os presentes); `nvidia-smi` ausente ⇒ VRAM fica vazia;
falha de chamada vira linha com status "falha_llm" — nunca exceção fatal.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import subprocess
import time
from pathlib import Path

import pandas as pd

from src.common.config import config
from src.common.llm import _criar_cliente, chat_stream
from src.insight.analista import limpar_label, montar_contexto
from src.insight.prompts import montar_prompt_rotulacao, montar_prompt_why
from src.rag.responder import montar_prompt_rag
from src.rag.retriever import retrieve

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Artefatos (entram/saem do diretório de pesquisa, não de dados/ — story §PSN).
# Monkeypatcháveis nos testes, como em src/rag/retriever.py.
# --------------------------------------------------------------------------
DIR_PESQUISA = Path("docs/research/2026-07-08-benchmark-llm-local")
AMOSTRA_PATH = DIR_PESQUISA / "amostra_benchmark.json"
BRUTOS_PATH = DIR_PESQUISA / "resultados_brutos.parquet"
PLANILHA_PATH = DIR_PESQUISA / "avaliacao_cega.csv"
MAPA_CEGO_PATH = DIR_PESQUISA / "mapa_cego.json"
RESULTADO_PATH = DIR_PESQUISA / "resultado-benchmark.md"

SCORES_PATH = "dados/scores/scores.parquet"
TOPIC_INFO_PATH = "dados/topics/topic_info.parquet"
DOC_TOPICS_PATH = "dados/topics/doc_topics.parquet"
CORPUS_PATH = "dados/raw/corpus.parquet"

# Shortlist do ADR-002 (findings.md §5) — A/B/C do protocolo §2.
SHORTLIST = ["qwen2.5:14b", "qwen3.5:9b", "gemma3:12b"]

# Budget de tokens das chamadas do benchmark — MAIOR que o de produção (512) e
# IGUAL para os 3 modelos (nada é tunado por modelo, protocolo §9). Motivo
# (achado desta story): modelos "thinking" (Qwen3.5) gastam >1.500 tokens de
# raciocínio ANTES do 1º token de conteúdo; com o contrato de produção eles não
# produzem NADA (`finish_reason=length`). O budget ampliado permite comparar a
# QUALIDADE; o custo real do raciocínio segue visível na latência medida, e a
# incompatibilidade com o contrato de 512 é registrada no relatório (AC5/AC6).
MAX_TOKENS_BENCHMARK = 4096

# --------------------------------------------------------------------------
# Estratificação da amostra (protocolo §3) — regras determinísticas.
# --------------------------------------------------------------------------
ESTRATO_TOPO_N = 6       # tópicos do topo do ranking (caso principal)
ESTRATO_NICHO_N = 2      # baixo suporte — testa se o modelo inventa
TOPICOS_RUIDOSOS = [5, 12]  # conectivos conhecidos (gate Fase 2) — robustez do rótulo
TOPICO_MULTITEMA = 0     # maior cluster (Artemis/Marte/meteoros/aurora) — testa foco

# Perguntas RAG congeladas (protocolo §3): 5 respondíveis pelo corpus +
# 3 pegadinhas (reusadas do E2E da 5.5 e do gate — recusa honesta esperada).
PERGUNTAS_RAG = [
    {"id": "q1", "respondivel": True,
     "pergunta": "O que aconteceu com a missão Artemis 2?"},
    {"id": "q2", "respondivel": True,
     "pergunta": "Por que o iPhone 16 da Apple está em destaque nas notícias?"},
    {"id": "q3", "respondivel": True,
     "pergunta": "O que as notícias dizem sobre memórias RAM DDR5?"},
    {"id": "q4", "respondivel": True,
     "pergunta": "Quais avanços no tratamento do câncer aparecem nas notícias?"},
    {"id": "q5", "respondivel": True,
     "pergunta": "O que as notícias dizem sobre as fases da Lua em julho de 2026?"},
    {"id": "q6", "respondivel": False,
     "pergunta": "Qual é a receita de bolo de cenoura?"},
    {"id": "q7", "respondivel": False,
     "pergunta": "Qual é o preço da ação da Apple hoje?"},
    {"id": "q8", "respondivel": False,
     "pergunta": "Qual smartphone devo comprar em 2027?"},
]

# Rubrica 1–5 (protocolo §5.1). A planilha cega traz uma coluna de nota por
# critério; o consolidador pondera fidelidade+fluência (núcleo do produto, §7).
CRITERIOS_RUBRICA = ["fluencia", "fidelidade", "relevancia", "citacao", "recusa"]
PESOS_QUALIDADE = {
    "fluencia": 2.0, "fidelidade": 2.0, "relevancia": 1.0, "citacao": 1.0, "recusa": 1.0,
}
FIDELIDADE_MINIMA = 3.0   # eliminatória (§7.3): média < 3 descarta o modelo
EMPATE_QUALIDADE = 0.3    # diferença ≤ 0,3 ⇒ empate técnico ⇒ decide desempenho


# --------------------------------------------------------------------------
# 1. Amostra congelada (AC2)
# --------------------------------------------------------------------------
def montar_amostra(scores: pd.DataFrame, topic_info: pd.DataFrame) -> dict:
    """Seleciona os ~12 tópicos estratificados + 8 perguntas RAG (protocolo §3).

    Regras determinísticas (mesmos artefatos ⇒ mesma amostra):
      - anomalia: tópicos com `is_anomaly` no ranking (Camada 2);
      - ruidosos/multi-tema: ids fixos conhecidos do projeto;
      - topo: maiores `trend_score` com `support_ok`, excluindo os já usados;
      - nicho: menores `size` com `support_ok=False` (desempate por topic_id).
    """
    m = scores.merge(topic_info[["topic_id", "label", "size"]], on="topic_id", how="left")
    ranking = m[(m["topic_id"] != -1) & (m["support_ok"])].sort_values(
        "trend_score", ascending=False
    )

    anomalia = ranking[ranking["is_anomaly"]]["topic_id"].head(1).tolist()
    reservados = set(anomalia) | set(TOPICOS_RUIDOSOS) | {TOPICO_MULTITEMA}
    topo = (
        ranking[~ranking["topic_id"].isin(reservados)]["topic_id"]
        .head(ESTRATO_TOPO_N)
        .tolist()
    )
    nicho = (
        m[(~m["support_ok"]) & (m["topic_id"] != -1)]
        .sort_values(["size", "topic_id"])["topic_id"]
        .head(ESTRATO_NICHO_N)
        .tolist()
    )

    estratos = (
        [(t, "topo") for t in topo]
        + [(t, "anomalia") for t in anomalia]
        + [(t, "ruidoso") for t in TOPICOS_RUIDOSOS]
        + [(t, "nicho") for t in nicho]
        + [(TOPICO_MULTITEMA, "multi_tema")]
    )
    labels = m.set_index("topic_id")["label"]
    topicos = [
        {"topic_id": int(t), "estrato": estrato, "label_ctfidf": str(labels.get(t, ""))}
        for t, estrato in estratos
    ]
    return {
        "descricao": "Amostra congelada do benchmark A/B/C (Story 5.6) — "
        "mesmos itens e ordem para todos os modelos.",
        "gerado_de": {"scores": SCORES_PATH, "topic_info": TOPIC_INFO_PATH},
        "topicos": topicos,
        "perguntas_rag": PERGUNTAS_RAG,
    }


def cmd_amostra() -> None:
    """Gera e congela `amostra_benchmark.json` a partir dos artefatos da Fase 3."""
    scores = pd.read_parquet(SCORES_PATH)
    topic_info = pd.read_parquet(TOPIC_INFO_PATH)
    amostra = montar_amostra(scores, topic_info)
    AMOSTRA_PATH.parent.mkdir(parents=True, exist_ok=True)
    AMOSTRA_PATH.write_text(
        json.dumps(amostra, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    logger.info(
        "Amostra congelada em %s (%d tópicos, %d perguntas RAG).",
        AMOSTRA_PATH, len(amostra["topicos"]), len(amostra["perguntas_rag"]),
    )


# --------------------------------------------------------------------------
# 2. Execução multi-modelo (AC1, AC3, AC6)
# --------------------------------------------------------------------------
def modelos_disponiveis() -> set[str]:
    """Ids servidos pelo endpoint OpenAI-compatible (vazio se endpoint fora)."""
    try:
        return {m.id for m in _criar_cliente().models.list()}
    except Exception as exc:  # noqa: BLE001 — endpoint fora ⇒ nenhum modelo
        logger.warning("Endpoint LLM inacessível (%s: %s).", type(exc).__name__, exc)
        return set()


def vram_mb() -> float | None:
    """VRAM em uso (MiB) via `nvidia-smi` — ``None`` se indisponível (AC6)."""
    try:
        saida = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        )
        return float(saida.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001 — sem GPU/driver, métrica fica vazia
        return None


def _descarregar_modelo(modelo: str) -> None:
    """Pede ao Ollama para liberar a VRAM do modelo (medição justa entre modelos).

    Best-effort: em endpoint não-Ollama (ou falha) apenas loga e segue.
    """
    try:
        subprocess.run(["ollama", "stop", modelo], capture_output=True, timeout=30, check=False)
    except Exception as exc:  # noqa: BLE001 — descarregar é otimização, não requisito
        logger.info("Não foi possível descarregar %s (%s) — seguindo.", modelo, exc)


def medir_chamada(messages: list[dict], *, temperature: float) -> dict:
    """Chama o LLM via `chat_stream` (5.1) medindo latência e throughput.

    Tokens são aproximados pelo nº de fragmentos do stream (no Ollama cada
    chunk carrega ~1 token) — aproximação declarada no relatório (AC6). Em
    modelos "thinking", o stream só expõe o CONTEÚDO: a latência do 1º token é
    até o 1º token útil (o raciocínio conta no tempo, não nos tokens).
    """
    inicio = time.perf_counter()
    primeiro_token_s: float | None = None
    pedacos: list[str] = []
    for pedaco in chat_stream(
        messages, temperature=temperature, max_tokens=MAX_TOKENS_BENCHMARK
    ):
        if primeiro_token_s is None:
            primeiro_token_s = time.perf_counter() - inicio
        pedacos.append(pedaco)
    total_s = time.perf_counter() - inicio
    tokens = len(pedacos)
    return {
        "saida": "".join(pedacos),
        "latencia_1o_token_s": primeiro_token_s,
        "latencia_total_s": total_s,
        "tokens_aprox": tokens,
        "tokens_por_s": tokens / total_s if tokens and total_s > 0 else None,
        "status": "ok" if pedacos else "falha_llm",
    }


def _linha(
    modelo: str, tarefa: str, item_id: str, item_ref: str, prompt: str, medida: dict
) -> dict:
    """Linha do `resultados_brutos.parquet` (uma por modelo × tarefa × item)."""
    return {
        "modelo": modelo,
        "tarefa": tarefa,
        "item_id": item_id,
        "item_ref": item_ref,
        "prompt": prompt,
        "vram_mb": vram_mb(),
        **medida,
    }


def executar_benchmark(modelos: list[str], amostra: dict) -> pd.DataFrame:
    """Percorre {modelos × amostra × T1/T2/T3} e devolve as medições (AC1/AC3).

    Os prompts de T1 e T3 são pré-montados UMA vez (independem do modelo — a
    amostra e o retriever são fixos); T2 usa o rótulo que o PRÓPRIO modelo deu
    em T1 (espelha o pipeline de produção do Analista IA, com fallback c-TF-IDF).
    """
    doc_topics = pd.read_parquet(DOC_TOPICS_PATH)
    corpus = pd.read_parquet(CORPUS_PATH)

    contextos = {
        t["topic_id"]: montar_contexto(t["topic_id"], doc_topics, corpus)
        for t in amostra["topicos"]
    }
    # Retrieval é idêntico para os 3 modelos — pré-computa (e evita medir o
    # encoder ST junto da inferência; a VRAM residual dele é igual para todos).
    prompts_rag = {
        p["id"]: montar_prompt_rag(p["pergunta"], retrieve(p["pergunta"]))
        for p in amostra["perguntas_rag"]
    }

    disponiveis = modelos_disponiveis()
    linhas: list[dict] = []
    for modelo in modelos:
        if modelo not in disponiveis:
            logger.warning("Modelo %s ausente no endpoint — PULANDO (AC6).", modelo)
            continue
        logger.info("=== Modelo %s ===", modelo)
        config.insight.model = modelo  # único ponto que varia (protocolo §2)

        sucesso_anterior = False
        for topico in amostra["topicos"]:
            tid, ref = topico["topic_id"], topico["label_ctfidf"]
            contexto = contextos[tid]

            msgs_t1 = montar_prompt_rotulacao(contexto)
            t1 = medir_chamada(msgs_t1, temperature=config.insight.temperature_batch)
            linhas.append(_linha(modelo, "T1", f"t{tid}", ref, msgs_t1[0]["content"], t1))

            label = limpar_label(t1["saida"]) if t1["status"] == "ok" else ref
            msgs_t2 = montar_prompt_why(label, contexto)
            t2 = medir_chamada(msgs_t2, temperature=config.insight.temperature_batch)
            linhas.append(_linha(modelo, "T2", f"t{tid}", ref, msgs_t2[0]["content"], t2))

            if t1["status"] == "ok" or t2["status"] == "ok":
                sucesso_anterior = True
            elif not sucesso_anterior:
                # Curto-circuito (decisão 4 do handoff): 1ª falha total sem
                # sucesso prévio ⇒ modelo caiu; não esperar N timeouts.
                logger.warning("%s presente mas sem resposta — abortando o modelo.", modelo)
                break
        else:
            for p in amostra["perguntas_rag"]:
                msgs_t3 = prompts_rag[p["id"]]
                t3 = medir_chamada(msgs_t3, temperature=config.insight.temperature_chat)
                linhas.append(
                    _linha(modelo, "T3", p["id"], p["pergunta"], msgs_t3[0]["content"], t3)
                )

        _descarregar_modelo(modelo)
    return pd.DataFrame(linhas)


def cmd_executar(modelos: list[str]) -> None:
    """Roda o benchmark e grava `resultados_brutos.parquet` (AC3)."""
    amostra = json.loads(AMOSTRA_PATH.read_text(encoding="utf-8"))
    modelo_original = config.insight.model
    try:
        brutos = executar_benchmark(modelos, amostra)
    finally:
        config.insight.model = modelo_original  # nunca vazar o override
    if brutos.empty:
        logger.warning("Nenhum modelo disponível — nada gravado.")
        return
    BRUTOS_PATH.parent.mkdir(parents=True, exist_ok=True)
    brutos.to_parquet(BRUTOS_PATH, index=False)
    logger.info(
        "%d medições de %d modelo(s) gravadas em %s.",
        len(brutos), brutos["modelo"].nunique(), BRUTOS_PATH,
    )


# --------------------------------------------------------------------------
# 3. Planilha de avaliação cega (AC4)
# --------------------------------------------------------------------------
def embaralhar_cego(brutos: pd.DataFrame, seed: int) -> tuple[pd.DataFrame, dict]:
    """Anonimiza e embaralha as saídas por item — sem revelar o modelo (AC4).

    Determinístico para a mesma seed (testável): a ordem dos grupos é fixa
    (sort) e um único `random.Random(seed)` embaralha cada item em sequência.

    Returns:
        ``(planilha, mapa)`` — a planilha traz `opcao_N` no lugar do modelo e
        colunas de nota vazias (rubrica 1–5); o mapa `tarefa|item|opcao →
        modelo` fica em arquivo separado (só abrir DEPOIS de pontuar).
    """
    rng = random.Random(seed)
    linhas: list[dict] = []
    mapa: dict[str, str] = {}
    avaliaveis = brutos[brutos["status"] == "ok"]
    for (tarefa, item_id), grupo in avaliaveis.groupby(["tarefa", "item_id"], sort=True):
        modelos = sorted(grupo["modelo"])
        rng.shuffle(modelos)
        for posicao, modelo in enumerate(modelos, start=1):
            registro = grupo[grupo["modelo"] == modelo].iloc[0]
            opcao = f"opcao_{posicao}"
            mapa[f"{tarefa}|{item_id}|{opcao}"] = modelo
            linhas.append(
                {
                    "tarefa": tarefa,
                    "item_id": item_id,
                    "item_ref": registro["item_ref"],
                    "prompt": registro["prompt"],
                    "opcao": opcao,
                    "saida": registro["saida"],
                    **{f"nota_{c}": None for c in CRITERIOS_RUBRICA},
                }
            )
    return pd.DataFrame(linhas), mapa


def cmd_planilha(seed: int) -> None:
    """Gera `avaliacao_cega.csv` + `mapa_cego.json` a partir dos brutos."""
    brutos = pd.read_parquet(BRUTOS_PATH)
    planilha, mapa = embaralhar_cego(brutos, seed)
    planilha.to_csv(PLANILHA_PATH, index=False)
    MAPA_CEGO_PATH.write_text(
        json.dumps({"seed": seed, "mapa": mapa}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info(
        "Planilha cega (%d linhas) em %s; mapa em %s — NÃO abrir o mapa antes de pontuar.",
        len(planilha), PLANILHA_PATH, MAPA_CEGO_PATH,
    )


# --------------------------------------------------------------------------
# 4. Consolidação (AC5, AC6)
# --------------------------------------------------------------------------
def _tabela_confiabilidade(brutos: pd.DataFrame) -> pd.DataFrame:
    """Chamadas sem NENHUM conteúdo por modelo (falha sob o budget do harness)."""
    tabela = (
        brutos.groupby("modelo")
        .agg(
            chamadas=("status", "size"),
            sem_saida=("status", lambda s: int((s != "ok").sum())),
        )
        .reset_index()
    )
    tabela["taxa_falha"] = (tabela["sem_saida"] / tabela["chamadas"]).round(2)
    return tabela


def _tabela_desempenho(brutos: pd.DataFrame) -> pd.DataFrame:
    """Médias de latência/throughput e pico de VRAM por modelo × tarefa."""
    ok = brutos[brutos["status"] == "ok"]
    return (
        ok.groupby(["modelo", "tarefa"])
        .agg(
            latencia_1o_token_s=("latencia_1o_token_s", "mean"),
            latencia_total_s=("latencia_total_s", "mean"),
            tokens_por_s=("tokens_por_s", "mean"),
            vram_pico_mb=("vram_mb", "max"),
            n=("saida", "size"),
        )
        .round(2)
        .reset_index()
    )


def consolidar_qualidade(avaliacoes: pd.DataFrame, mapa: dict) -> pd.DataFrame:
    """Notas médias por critério/modelo a partir das planilhas preenchidas.

    `avaliacoes` é a concatenação das planilhas dos avaliadores (≥ 2, protocolo
    §6.4); o mapa cego reatribui cada `opcao_N` ao modelo real.
    """
    df = avaliacoes.copy()
    chave = df["tarefa"] + "|" + df["item_id"] + "|" + df["opcao"]
    df["modelo"] = chave.map(mapa)
    notas = df.melt(
        id_vars=["modelo"],
        value_vars=[f"nota_{c}" for c in CRITERIOS_RUBRICA],
        var_name="criterio",
        value_name="nota",
    ).dropna(subset=["nota", "modelo"])
    notas["criterio"] = notas["criterio"].str.removeprefix("nota_")
    media = notas.groupby(["modelo", "criterio"])["nota"].mean().unstack()

    presentes = [c for c in CRITERIOS_RUBRICA if c in media.columns]
    peso_total = sum(PESOS_QUALIDADE[c] for c in presentes)
    media["qualidade_ponderada"] = (
        sum(media[c] * PESOS_QUALIDADE[c] for c in presentes) / peso_total
    )
    return media.round(2)


def decidir(qualidade: pd.DataFrame, desempenho: pd.DataFrame) -> tuple[str, str]:
    """Aplica a regra de decisão do protocolo §7 → (vencedor, justificativa)."""
    candidatos = qualidade.copy()
    eliminados = []
    if "fidelidade" in candidatos.columns:
        eliminados = candidatos[candidatos["fidelidade"] < FIDELIDADE_MINIMA].index.tolist()
        candidatos = candidatos[candidatos["fidelidade"] >= FIDELIDADE_MINIMA]
    if candidatos.empty:
        return "", "Todos os modelos eliminados por fidelidade < 3 (alucinação frequente)."

    ordenados = candidatos["qualidade_ponderada"].sort_values(ascending=False)
    lider, nota_lider = ordenados.index[0], ordenados.iloc[0]
    empatados = ordenados[nota_lider - ordenados <= EMPATE_QUALIDADE].index.tolist()

    justificativa = f"maior qualidade ponderada ({nota_lider:.2f})"
    vencedor = lider
    if len(empatados) > 1:
        lat = (
            desempenho[desempenho["modelo"].isin(empatados)]
            .groupby("modelo")["latencia_total_s"].mean().sort_values()
        )
        vencedor = lat.index[0]
        justificativa = (
            f"empate técnico em qualidade (Δ ≤ {EMPATE_QUALIDADE}) entre "
            f"{', '.join(empatados)} — decidido por menor latência média "
            f"({lat.iloc[0]:.1f}s)"
        )
    if eliminados:
        justificativa += (
            f"; eliminado(s) por fidelidade < {FIDELIDADE_MINIMA:.0f}: {', '.join(eliminados)}"
        )
    return vencedor, justificativa


def _md_tabela(df: pd.DataFrame) -> str:
    """DataFrame → tabela Markdown (sem dependência extra)."""
    df = df.reset_index() if df.index.name else df
    linhas = ["| " + " | ".join(str(c) for c in df.columns) + " |",
              "|" + "---|" * len(df.columns)]
    for _, row in df.iterrows():
        linhas.append("| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |")
    return "\n".join(linhas)


def gerar_relatorio(
    brutos: pd.DataFrame,
    qualidade: pd.DataFrame | None,
    avaliadores: int,
) -> str:
    """Monta o `resultado-benchmark.md` (AC5) com limitações declaradas (AC6)."""
    desempenho = _tabela_desempenho(brutos)
    modelos_medidos = sorted(brutos["modelo"].unique())
    ausentes = [m for m in SHORTLIST if m not in modelos_medidos]

    partes = [
        "# Resultado do benchmark A/B/C — LLM local (Story 5.6)",
        "",
        f"**Modelos medidos:** {', '.join(modelos_medidos)}"
        + (f" — **ausentes (pulados):** {', '.join(ausentes)}" if ausentes else ""),
        f"**Protocolo:** `protocolo-empirico.md` | **Amostra:** `{AMOSTRA_PATH.name}` "
        f"(congelada) | **Brutos:** `{BRUTOS_PATH.name}`",
        "",
        "## Desempenho (medição automática)",
        "",
        _md_tabela(desempenho),
        "",
        "> Tokens aproximados pelo nº de fragmentos do stream (~1 token/chunk no "
        "Ollama). VRAM = `memory.used` global da GPU (inclui o encoder do "
        "retriever, ~igual para todos os modelos — comparação justa). Budget "
        f"uniforme de {MAX_TOKENS_BENCHMARK} tokens por chamada (> produção, 512): "
        "modelos *thinking* gastam >1.500 tokens de raciocínio antes do 1º token "
        "de conteúdo e NÃO produzem saída sob o contrato de produção — a latência "
        "do 1º token aqui é até o 1º token de CONTEÚDO (raciocínio conta no tempo, "
        "não nos tokens).",
        "",
        "## Confiabilidade (chamadas sem saída sob o budget do harness)",
        "",
        _md_tabela(_tabela_confiabilidade(brutos)),
        "",
        "> Falha = a chamada terminou sem NENHUM token de conteúdo (ex.: modelo "
        "*thinking* estourou o budget só raciocinando). Itens com falha ficam "
        "fora da avaliação cega daquele modelo.",
        "",
    ]

    if qualidade is not None and not qualidade.empty:
        vencedor, justificativa = decidir(qualidade, desempenho)
        partes += [
            f"## Qualidade (avaliação cega, {avaliadores} avaliador(es) — rubrica 1–5)",
            "",
            _md_tabela(qualidade.reset_index()),
            "",
            f"Pesos: fidelidade ×{PESOS_QUALIDADE['fidelidade']:.0f}, "
            f"fluência ×{PESOS_QUALIDADE['fluencia']:.0f}, demais ×1 "
            f"(protocolo §7 — fidelidade < {FIDELIDADE_MINIMA:.0f} elimina).",
            "",
            "## Recomendação",
            "",
        ]
        if vencedor:
            partes.append(f"**Vencedor: `{vencedor}`** — {justificativa}.")
            if vencedor != config.insight.model:
                partes.append(
                    f"\n> ⚠️ O vencedor difere do default atual "
                    f"(`insight.model: {config.insight.model}`): atualizar "
                    f"`config/config.yaml` e registrar no Change Log do ADR-002."
                )
            else:
                partes.append(
                    "\n> Confirma o default do ADR-002 — nenhuma mudança de config necessária."
                )
        else:
            partes.append(f"**Sem vencedor** — {justificativa}")
    else:
        partes += [
            "## Qualidade (avaliação cega) — PENDENTE",
            "",
            "A pontuação humana ainda não foi realizada. Próximos passos "
            "(protocolo §6.4): ≥ 2 integrantes preenchem cópias de "
            f"`{PLANILHA_PATH.name}` (rubrica 1–5, SEM abrir `{MAPA_CEGO_PATH.name}`) "
            "e rodam `poetry run python scripts/benchmark_llm.py consolidar "
            "--avaliacoes <arquivos.csv>`.",
        ]

    partes += [
        "",
        "## Limitações declaradas",
        "",
        f"- Amostra pequena ({len(brutos['item_id'].unique())} itens): sinal "
        "**qualitativo**, não significância estatística (protocolo §9).",
        "- Mesma quantização (Q4 default do Ollama) e mesmos prompts de produção "
        "para todos — nenhum prompt foi tunado por modelo.",
    ]
    if ausentes:
        partes.append(
            f"- Modelo(s) não medidos nesta execução: {', '.join(ausentes)} "
            "(ausentes no endpoint — o harness pulou com log, AC6)."
        )
    if avaliadores == 1:
        partes.append(
            "- Apenas 1 avaliador até o momento — o protocolo pede ≥ 2 com "
            "checagem de concordância; tratar como resultado preliminar."
        )
    partes.append("")
    return "\n".join(partes)


def cmd_consolidar(avaliacoes_paths: list[str]) -> None:
    """Consolida brutos (+ avaliações preenchidas, se houver) em Markdown."""
    brutos = pd.read_parquet(BRUTOS_PATH)
    qualidade = None
    n_avaliadores = len(avaliacoes_paths)
    if avaliacoes_paths:
        mapa = json.loads(MAPA_CEGO_PATH.read_text(encoding="utf-8"))["mapa"]
        avaliacoes = pd.concat([pd.read_csv(p) for p in avaliacoes_paths], ignore_index=True)
        qualidade = consolidar_qualidade(avaliacoes, mapa)
    relatorio = gerar_relatorio(brutos, qualidade, n_avaliadores)
    RESULTADO_PATH.write_text(relatorio, encoding="utf-8")
    logger.info("Relatório consolidado em %s.", RESULTADO_PATH)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    sub.add_parser("amostra", help="Congela amostra_benchmark.json (AC2)")

    p_exec = sub.add_parser("executar", help="Roda {modelos × amostra × T1/T2/T3} (AC1/AC3)")
    p_exec.add_argument(
        "--modelos", default=",".join(SHORTLIST),
        help=f"Lista separada por vírgula (default: {','.join(SHORTLIST)})",
    )

    p_plan = sub.add_parser("planilha", help="Gera a planilha de avaliação cega (AC4)")
    p_plan.add_argument(
        "--seed", type=int, default=42, help="Seed do embaralhamento (determinístico)"
    )

    p_cons = sub.add_parser("consolidar", help="Gera resultado-benchmark.md (AC5)")
    p_cons.add_argument(
        "--avaliacoes", nargs="*", default=[],
        help="CSVs preenchidos pelos avaliadores (vazio ⇒ relatório parcial, só desempenho)",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.comando == "amostra":
        cmd_amostra()
    elif args.comando == "executar":
        cmd_executar([m.strip() for m in args.modelos.split(",") if m.strip()])
    elif args.comando == "planilha":
        cmd_planilha(args.seed)
    elif args.comando == "consolidar":
        cmd_consolidar(args.avaliacoes)


if __name__ == "__main__":
    main()
