"""Shim de retrocompatibilidade para scripts/run_quant_pipeline.py."""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o diretório raiz e scripts estejam acessíveis
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_quant_pipeline import main

if __name__ == "__main__":
    main()
