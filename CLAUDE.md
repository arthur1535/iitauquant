# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This repo ("iitauquant") holds two related but independent quant research tracks built for the "Desafio II Itaú Quant" challenge:

- **Fundo LASTRO** (`quant_fund/`): a multi-sleeve systematic fund (factor/quality, small-cap momentum, cash) with a macro risk overlay (BAA10Y credit spread + NFCI), producing the official `relatorios/AAKR.pdf` deliverable.
- **Laboratório Momentum ATR & Paper OMS** (`src/`): a trend-following Momentum ATR strategy with a causal backtest engine, walk-forward/OOS validation, and a paper-only Order Management System (FastAPI + Cloudflare Worker webhook) that only ever simulates orders.

These two tracks have separate config, data, scripts, and test files — check which track a task belongs to before touching shared-sounding files.

## Commands

### Python environment
```bash
python -m venv .venv
pip install -r requirements.txt          # full deps
pip install -r requirements-tradingview.txt  # OMS/backtest-only deps (fastapi, vectorbt, optuna, duckdb...)
```
Python 3.11+ required (3.12 recommended). Package layout uses `src/` (see `[tool.setuptools] package-dir = {"" = "src"}` in `pyproject.toml`); `quant_fund/` is a separate top-level package.

### Tests
```bash
# Full Python suite (139 tests)
python -m pytest tests/ -q

# Single test file / single test
python -m pytest tests/test_momentum_backtest.py -q
python -m pytest tests/test_server_oms.py::test_name -q

# Cloudflare Worker suite (37 tests, Node's built-in test runner)
node --test infra/cloudflare/test/worker.test.mjs
# or, from infra/cloudflare/
npm test
```

### Running the fund pipeline (LASTRO / AAKR report)
```bash
python scripts/backtest_auditoria.py          # preliminary backtest + bias audit
python scripts/auditar_vintages_macro.py      # point-in-time ALFRED/FRED vintage audit
python scripts/diagnostico_overlay.py         # overlay attribution, sensitivity, statistical gate
python scripts/graficos_relatorio.py          # render official figures R1..R7
python scripts/build_relatorio.py             # compile relatorios/AAKR.pdf and AAKR_retrato.pdf

python scripts/run_quant_pipeline.py --input-dir dados --output-dir resultados/quant
```

### Running the Momentum ATR lab
```bash
python scripts/run_global_momentum_research.py     # research on global liquid leaders
python scripts/analisar_mercado_chines.py           # China ETFs/stocks study
python scripts/run_out_of_sample_audit.py --symbol SPY --dry-run   # formal OOS audit, temporal contract
```

### Paper OMS server (simulation only)
```bash
cp .env.example .env   # set TRADINGVIEW_WEBHOOK_SECRET (>=32 random chars), never commit real value
python -m uvicorn src.server.app:app --host 127.0.0.1 --port 8000
```
There is no live/real trading mode — `src/server/config.py` hardcodes `mode: Literal["paper"] = "paper"`; any attempt to change it is expected to fail closed.

## Architecture

### Momentum ATR research → OOS pipeline
```
point-in-time manifest + adjusted OHLCV
  -> quality/provenance validation
  -> signal computed on close[t] -> pending order -> execution strictly at open[t+1]
  -> grid/Optuna search on IS 70% -> selection -> OOS 30% + walk-forward
  -> metrics, DSR, stress tests, reproducible checkpoints
```
Key invariant: the decision price and the execution price are distinct events. Stops are evaluated against OHLC — if the open gaps through the stop, the fill happens at the open; otherwise an intrabar touch fills at the stop level. Standard costs: 15 bps on entry and 15 bps on exit. This look-ahead discipline is what `src/backtest/engine.py`, `src/backtest/validation.py`, and `tests/test_momentum_backtest.py` / `tests/test_oos_validation.py` exist to enforce — do not "simplify" fills to same-bar close execution.

### Alert/webhook path (paper-only, edge to OMS)
```
TradingView --(POST JSON)--> Cloudflare Worker
  -> IP allowlist + body size limit
  -> HMAC SHA-256 over the exact raw JSON bytes
  --> Cloudflare Tunnel / HTTPS origin
  --> FastAPI (src/server/app.py, security.py)
       -> compare_digest + payload timestamp/nonce (replay prevention)
       -> schema/allowlist/limit/idempotency checks
       -> append-only event written to SQLite (WAL mode)
  --> Paper OMS (no real broker adapter exists in this codebase)
```
Trust boundaries worth preserving when touching this path (see `docs/ARCHITECTURE_MOMENTUM.md`, `docs/SECURITY_MODEL.md`):
- TradingView alerts are untrusted input.
- Only the Worker knows the public origin; only Worker + FastAPI know the shared HMAC secret.
- SQLite is a local audit ledger, not proof of a real execution.
- A real broker (e.g. IBKR) is intentionally out of process — do not add one.
- Market data is only ever treated as "real" when it carries provenance; synthetic series must be explicitly labeled as such, never silently substituted for missing real data.
- The FastAPI handler must respond in well under 3s — persistence/response stays synchronous and small; heavy analysis must not sit in the webhook request path.

### Source layout
- `src/iitauquant_data/` — ingestion, normalization, caching pipeline for prices/fundamentals/macro (has its own CLI: `iitauquant-data`).
- `src/backtest/` — causal backtest engine, grid/Optuna optimization, DSR/statistics, walk-forward validation, stress tests.
- `src/strategies/` — Momentum ATR strategy implementation and OHLCV validation.
- `src/automation/` — task scheduler/runner (has CLI entry point `iitauquant-paper` = `automation.__main__:main`).
- `src/server/` — FastAPI paper OMS: `app.py` (routes), `security.py` (HMAC/replay), `storage.py`/`paper_ledger.py` (SQLite WAL), `config.py` (paper-only enforcement).
- `src/antigravity/` — prompts/manifests for autonomous research runs (not executable code).
- `quant_fund/` — the separate LASTRO fund package: `sleeve1/2/3.py`, `risk_overlay.py` (BAA10Y + NFCI hysteresis de-risking), `portfolio.py` (weighting/consolidation), `validation.py` (DSR/PSR/block bootstrap), `pipeline.py` (end-to-end run).
- `tradingview/` — Pine v5/v6 scripts (indicators, strategy, dashboard) that must stay behaviorally in parity with the Python backtest engine; see `docs/TRADINGVIEW_CREATOR.md`.
- `infra/cloudflare/` — the webhook-terminating Worker (HMAC + IP allowlist), its own Node test suite, and tunnel config.
- `data/` vs `dados/`: `data/` is the daily market Parquet cache + the paper OMS SQLite DB (Momentum lab); `dados/` is the monthly/macro data layer for the LASTRO fund (SEC XBRL, FRED series). Don't conflate the two when adding data.

## Multi-agent collaboration in this repo

This repo is actively worked on concurrently by multiple AI agents/tools (not just Claude Code):

- **`AGENT_SYNC.md`** is the live coordination log between agents (Antigravity, ChatGPT/Codex, etc.). Before editing, check its "Locks de Trabalho Ativo" table for files currently claimed by another agent, and declare your own scope/files there before starting non-trivial work, to avoid merge conflicts and overwrites.
- **`.agents/`** defines Antigravity-specific sub-agent roles (`quant-lead`, `backtest-engineer`, `walkforward-researcher`, `data-auditor`, `api-security`, `pine-reviewer`, `test-auditor`, `release-auditor`) used via Antigravity's `/teamwork-preview`; not directly invoked from Claude Code, but useful for understanding division-of-labor conventions already in use.
- **`log_uso_genai.csv`** is a formal audit trail of GenAI usage required by the challenge rules (counts for 15% of the grade) — interventions by AI agents are expected to be logged here.
- **`docs/ACCEPTANCE_CHECKLIST.md`** lists 17 formally audited acceptance criteria for this project; changes that regress any of them should be treated as blocking.

## Hard constraints (do not relax)

- **Paper-only, always.** No real broker connections, no paid API keys, no live order routing, no deployments that could incur cost. `src/server/config.py`'s paper-mode lock and the Worker's lack of a deployed origin are intentional — do not "complete" them into a live path.
- **No look-ahead.** Signals decided at `close[t]` execute at `open[t+1]`, never same-bar.
- **Never substitute synthetic data for missing real data without an explicit label.** If real data is unavailable, say so — don't silently fill gaps with synthetic series.
