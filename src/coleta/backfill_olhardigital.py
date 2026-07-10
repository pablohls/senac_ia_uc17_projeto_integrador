"""
Prova de Conceito — Backfill histórico do Olhar Digital via sitemap.

Valida a fonte de dados recomendada no brief (docs/brief.md) e na pesquisa
docs/research/2026-06-08-backfill-historico/findings.md.

Estratégia:
  1. Lê o sitemap index (organizado por mês).
  2. Seleciona os sitemaps dos últimos N meses.
  3. Extrai URLs de artigos + data + categoria (data e categoria vêm na própria URL).
  4. (Opcional) Raspa o texto limpo de cada artigo com `trafilatura`.
  5. Salva um dataset congelado em CSV: data, titulo, texto, fonte, categoria, url.

O núcleo (passos 1-3) roda só com a biblioteca padrão do Python — zero instalação.
A extração de texto (passo 4) precisa de: pip install trafilatura

Uso:
  # Só listar URLs datadas dos últimos 2 meses (rápido, sem baixar texto):
  python backfill_olhardigital.py --meses 2 --sem-texto

  # Coletar texto dos últimos 4 meses, só categoria ciência/espaço, limite p/ teste:
  python backfill_olhardigital.py --meses 4 --categoria ciencia-e-espaco --limite 50

  # Backfill completo de 6 meses:
  python backfill_olhardigital.py --meses 6 --saida dados/olhardigital.csv
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

SITEMAP_INDEX = "https://olhardigital.com.br/sitemap.xml"
FONTE = "olhardigital"
USER_AGENT = "SONAR-PoC/0.1 (projeto integrador IA; coleta academica)"
SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

# /2026/06/06/ciencia-e-espaco/titulo-do-artigo/
URL_RE = re.compile(r"olhardigital\.com\.br/(\d{4})/(\d{2})/(\d{2})/([^/]+)/([^/]+)/?$")


def baixar(url: str, timeout: int = 30) -> bytes:
    """GET simples com User-Agent definido."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def meses_alvo(n: int) -> list[str]:
    """Retorna os últimos N rótulos 'AAAA-MM' (incluindo o mês corrente)."""
    hoje = datetime.now(UTC)
    rotulos = []
    ano, mes = hoje.year, hoje.month
    for _ in range(n):
        rotulos.append(f"{ano:04d}-{mes:02d}")
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
    return rotulos


def listar_sitemaps_mensais(n_meses: int) -> list[str]:
    """Lê o index e devolve os sub-sitemaps dos últimos N meses."""
    raiz = ET.fromstring(baixar(SITEMAP_INDEX))
    alvos = set(meses_alvo(n_meses))
    selecionados = []
    for loc in raiz.findall(".//sm:sitemap/sm:loc", SITEMAP_NS):
        url = (loc.text or "").strip()
        # nomes do tipo sitemap_post_2026-05_1.xml
        m = re.search(r"sitemap_post_(\d{4}-\d{2})", url)
        if m and m.group(1) in alvos:
            selecionados.append(url)
    return sorted(selecionados, reverse=True)


def parse_artigo(url: str):
    """Extrai (data_iso, categoria) da URL do artigo, ou None se não bater."""
    m = URL_RE.search(url)
    if not m:
        return None
    ano, mes, dia, categoria, _slug = m.groups()
    return f"{ano}-{mes}-{dia}", categoria


def coletar_urls(n_meses: int, categoria: str | None, pausa: float):
    """Itera os sitemaps mensais e devolve lista de registros (sem texto ainda)."""
    registros = []
    vistos = set()
    sitemaps = listar_sitemaps_mensais(n_meses)
    print(f"[i] {len(sitemaps)} sitemap(s) mensal(is) selecionado(s).", file=sys.stderr)

    for sm_url in sitemaps:
        try:
            raiz = ET.fromstring(baixar(sm_url))
        except Exception as e:  # noqa: BLE001
            print(f"[!] Falha em {sm_url}: {e}", file=sys.stderr)
            continue

        for loc in raiz.findall(".//sm:url/sm:loc", SITEMAP_NS):
            url = (loc.text or "").strip()
            if url in vistos:
                continue
            info = parse_artigo(url)
            if not info:
                continue
            data_iso, cat = info
            if categoria and cat != categoria:
                continue
            vistos.add(url)
            registros.append(
                {
                    "data": data_iso,
                    "categoria": cat,
                    "fonte": FONTE,
                    "url": url,
                    "titulo": "",
                    "texto": "",
                }
            )
        print(f"[i] {sm_url.split('/')[-1]}: acumulado {len(registros)} artigos.", file=sys.stderr)
        time.sleep(pausa)

    return registros


def extrair_texto(registros, pausa: float, limite: int | None):
    """Raspa título e texto de cada artigo com trafilatura (se instalado)."""
    try:
        import trafilatura  # type: ignore
    except ImportError:
        print(
            "[!] trafilatura não instalado — pulando extração de texto.\n"
            "    Instale com: pip install trafilatura",
            file=sys.stderr,
        )
        return registros

    alvo = registros[:limite] if limite else registros
    total = len(alvo)
    for i, reg in enumerate(alvo, 1):
        try:
            html = baixar(reg["url"]).decode("utf-8", errors="replace")
            texto = trafilatura.extract(html, include_comments=False) or ""
            reg["texto"] = texto.replace("\n", " ").strip()
            meta = trafilatura.extract_metadata(html)
            if meta and meta.title:
                reg["titulo"] = meta.title.strip()
        except Exception as e:  # noqa: BLE001
            print(f"[!] {reg['url']}: {e}", file=sys.stderr)
        if i % 25 == 0 or i == total:
            print(f"[i] texto {i}/{total}", file=sys.stderr)
        time.sleep(pausa)
    return registros


def salvar_csv(registros, caminho: Path):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    campos = ["data", "titulo", "texto", "fonte", "categoria", "url"]
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for reg in registros:
            w.writerow({c: reg.get(c, "") for c in campos})


def main():
    p = argparse.ArgumentParser(description="Backfill Olhar Digital via sitemap (PoC).")
    p.add_argument("--meses", type=int, default=3, help="quantos meses para trás (default 3)")
    p.add_argument(
        "--categoria", default=None, help="filtrar por categoria da URL (ex.: ciencia-e-espaco)"
    )
    p.add_argument(
        "--sem-texto",
        action="store_true",
        help="só listar URLs datadas, sem baixar o texto dos artigos",
    )
    p.add_argument(
        "--limite",
        type=int,
        default=None,
        help="máximo de artigos para extrair texto (útil em teste)",
    )
    p.add_argument(
        "--pausa", type=float, default=1.0, help="segundos entre requisições (polidez; default 1.0)"
    )
    p.add_argument("--saida", default="dados/olhardigital.csv", help="arquivo CSV de saída")
    args = p.parse_args()

    registros = coletar_urls(args.meses, args.categoria, pausa=min(args.pausa, 0.5))
    print(f"[✓] {len(registros)} URLs de artigos datadas coletadas.", file=sys.stderr)

    if not args.sem_texto:
        registros = extrair_texto(registros, pausa=args.pausa, limite=args.limite)

    saida = Path(args.saida)
    salvar_csv(registros, saida)
    print(f"[✓] Dataset salvo em {saida.resolve()} ({len(registros)} linhas).", file=sys.stderr)


if __name__ == "__main__":
    main()
