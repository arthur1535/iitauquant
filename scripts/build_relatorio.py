"""Monta o relatório final: embute as figuras no HTML e imprime os PDFs.

Duas montagens a partir do mesmo conteúdo e das mesmas figuras:

  AAKR.pdf          5 páginas em 16:9 horizontal — o formato exigido pelo edital
  AAKR_retrato.pdf  5 páginas em A4 retrato — versão em folha em pé

Os arquivos .html correspondentes ficam ao lado, autocontidos (imagens em data URI).
"""

from __future__ import annotations

import base64
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "resultados" / "graficos"
REPORTS = ROOT / "relatorios"

MONTAGENS = [
    ("16:9 horizontal (edital)", REPORTS / "template_relatorio.html",
     REPORTS / "AAKR.html", REPORTS / "AAKR.pdf"),
    ("A4 retrato", REPORTS / "template_relatorio_retrato.html",
     REPORTS / "AAKR_retrato.html", REPORTS / "AAKR_retrato.pdf"),
]

FIGURE_MAP = {
    "R1": "R1_ponto_cego.png",
    "R2": "R2_atribuicao.png",
    "R3": "R3_curvas.png",
    "R4": "R4_seguro.png",
    "R5": "R5_duration.png",
    "R6": "R6_diversificacao.png",
    "R7": "R7_premios.png",
}


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def word_count(html: str) -> int:
    """Conta apenas o texto visível, sem CSS, marcação nem atributos."""
    text = re.sub(r"<style.*?</style>", " ", html, flags=re.S)
    text = re.sub(r"<svg.*?</svg>", " ", text, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return len([w for w in re.split(r"\s+", text) if any(c.isalnum() for c in w)])


def find_chrome() -> str | None:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


def main() -> int:
    missing = [n for n in FIGURE_MAP.values() if not (FIGURES / n).exists()]
    if missing:
        print(f"ERRO: figuras ausentes: {missing}\nRode antes: python scripts/graficos_relatorio.py")
        return 1
    figures = {key: data_uri(FIGURES / name) for key, name in FIGURE_MAP.items()}
    chrome = find_chrome()

    for label, template, html_out, pdf_out in MONTAGENS:
        if not template.exists():
            print(f"AVISO: template ausente para {label}: {template.name}")
            continue
        html = template.read_text(encoding="utf-8")
        for key, uri in figures.items():
            html = html.replace(f"{{{{{key}}}}}", uri)
        html_out.write_text(html, encoding="utf-8")
        print(f"\n{label}")
        print(f"  HTML   {html_out.relative_to(ROOT)}  ({len(html.encode()) / 1e6:.2f} MB)")
        print(f"  Texto  {word_count(html)} palavras visíveis  (referência do edital: ~750)")
        if not chrome:
            print("  AVISO: Chrome/Chromium não encontrado; imprima o HTML manualmente.")
            continue
        subprocess.run(
            [
                chrome, "--headless", "--disable-gpu", "--no-sandbox",
                "--no-pdf-header-footer", "--run-all-compositor-stages-before-draw",
                "--virtual-time-budget=12000",
                f"--print-to-pdf={pdf_out}", html_out.as_uri(),
            ],
            check=True,
            capture_output=True,
        )
        print(f"  PDF    {pdf_out.relative_to(ROOT)}  ({pdf_out.stat().st_size / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
