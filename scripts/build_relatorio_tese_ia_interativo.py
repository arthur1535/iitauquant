"""Gera a página interativa da tese Infraestrutura de IA.

Lê o snapshot congelado e as tabelas de results/tese_ia_infra/ (produzidos por
scripts/run_tese_ia_infraestrutura.py) e escreve um HTML autocontido, com
gráficos interativos, em relatorios/. Não baixa dados.

Uso:
    python scripts/run_tese_ia_infraestrutura.py        # se os resultados ainda não existirem
    python scripts/build_relatorio_tese_ia_interativo.py
"""

from __future__ import annotations

import html
import json
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "scripts", ROOT / "src"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import run_tese_ia_infraestrutura as tese  # noqa: E402

OUT = ROOT / "relatorios" / f"tese_ia_infraestrutura_interativo_{tese.REPORT_DATE}.html"


def collect_data() -> dict:
    """Curvas semanais, exposição mensal por camada e tabelas já calculadas pela estratégia."""

    ds = tese.load_snapshot()
    closes, volumes, bh = tese.build_panels(ds)
    res = tese.run_sleeves(ds, tese.EXECUTION)
    atr = pd.DataFrame({t: r.equity_curve["daily_return"] for t, r in res.items()}).reindex(closes.index)
    openr = tese.run_sleeves(ds, replace(tese.EXECUTION, liquidate_at_end=False))
    pos = pd.DataFrame({t: r.equity_curve["position"] for t, r in openr.items()}).reindex(closes.index).fillna(0)
    sched = tese.target_weight_schedule(closes, volumes, tese.PESOS_CAMADAS, tese.GRUPO_CAMADA)
    base, scaled = tese.run_principal(atr, sched)
    bhp = tese.simulate_rebalanced_portfolio(bh, sched)
    window = scaled.index
    series = {
        "principal": scaled["daily_return"],
        "bh": bhp.curve["daily_return"],
        "smh": ds["SMH"]["close"].pct_change().reindex(window).fillna(0.0),
        "qqq": ds["QQQ"]["close"].pct_change().reindex(window).fillna(0.0),
    }
    for k in ("smh", "qqq"):
        series[k].iloc[0] = 0.0
    nav = pd.DataFrame({k: 100 * (1 + v).cumprod() for k, v in series.items()})
    dd = nav / nav.cummax() - 1
    wk_nav = nav.resample("W-FRI").last()
    wk_dd = dd.resample("W-FRI").min()
    curves = {"dates": [d.strftime("%Y-%m-%d") for d in wk_nav.index],
              "nav": {k: [round(x, 2) for x in wk_nav[k]] for k in nav},
              "dd": {k: [round(x * 100, 2) for x in wk_dd[k]] for k in nav},
              "final": {k: round(float(nav[k].iloc[-1]), 1) for k in nav},
              "maxdd": {k: round(float(dd[k].min() * 100), 1) for k in nav}}

    eff = base.weights * pos.reindex(base.weights.index)
    eff = eff.mul(scaled["multiplier"], axis=0)
    layers = {c: eff[[a.ticker for a in tese.ATIVOS if a.camada == c]].sum(axis=1) for c in tese.CAMADAS}
    mon = pd.DataFrame(layers).resample("ME").mean() * 100
    exposure = {"months": [d.strftime("%Y-%m") for d in mon.index],
                "layers": {c: [round(x, 1) for x in mon[c]] for c in tese.CAMADAS}}

    R = tese.RESULTS_DIR
    read = lambda f: pd.read_csv(R / f)
    out = {
        "curves": curves, "exposure": exposure,
        "variants": read("metricas_variantes.csv").to_dict("records"),
        "subperiods": read("metricas_subperiodos.csv").to_dict("records"),
        "annual": read("retornos_anuais.csv").to_dict("records"),
        "loo": read("robustez_exclusao_ativo.csv").to_dict("records"),
        "stress": read("estresse_custos.csv").to_dict("records"),
        "assets": read("metricas_individuais.csv").to_dict("records"),
        "positions": read("sinais_atuais.csv").fillna("").to_dict("records"),
        "stats": json.loads((R / "estatisticas.json").read_text()),
        "ativos": [{"ticker": a.ticker, "empresa": a.empresa, "camada": a.camada, "peso": a.peso, "papel": a.papel, "risco": a.risco} for a in tese.ATIVOS],
    }
    # Ida e volta em JSON: tipos nativos e falha explícita se houver NaN.
    return json.loads(json.dumps(out, ensure_ascii=False, allow_nan=False, default=float))


D = collect_data()

MINUS = "−"
CAMADAS = {
    "computacao": ("Chips e computação", "s1"),
    "infraestrutura": ("Infraestrutura do data center", "s2"),
    "energia": ("Geração de energia", "s3"),
    "especulativo": ("Satélites especulativos", "s4"),
}


def esc(v):
    return html.escape(str(v))


def num(v, d=2):
    s = f"{abs(v):,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return (MINUS if v < 0 else "") + s


def pct(v, d=1, sign=False):
    s = num(abs(v) * 100, d) + "%"
    if v < 0:
        return MINUS + s
    return ("+" if sign and v > 0 else "") + s


def signed(v, d=1):
    cls = "up" if v > 0 else ("down" if v < 0 else "")
    return f"<td class='{cls}'>{pct(v, d, True)}</td>"


def dd(v, d=1):
    return f"<td>{pct(v, d)}</td>"


def date_br(s):
    return f"{s[8:10]}/{s[5:7]}/{s[:4]}"


st = D["stats"]
V = {r["variante"]: r for r in D["variants"]}
P, BH, QQQ, SMH = V["ATR_CAMADAS_VT"], V["BH_CAMADAS"], V["QQQ_BH"], V["SMH_BH"]
ativos = D["ativos"]
positions = {r["ticker"]: r for r in D["positions"]}
assets = {r["ticker"]: r for r in D["assets"]}
n_long = sum(1 for r in D["positions"] if r["sinal"] == "comprado")
ep = st["episodio"] if "episodio" in st else None

# ---------------------------------------------------------------- hero: da usina ao chip
stages = [
    ("energia", "Geração", "Turbinas, usinas nucleares e a gás, células a combustível"),
    ("infraestrutura", "Rede e data center", "Linhas, subestações, energia crítica e refrigeração"),
    ("computacao", "Servidores e chips", "Racks, GPUs, memória HBM e semicondutores de potência"),
]
stage_html = []
for key, name, desc in stages:
    members = [a for a in ativos if a["camada"] == key]
    weight = sum(a["peso"] for a in members)
    chips = "".join(
        f"<li><span class='tk'>{a['ticker']}</span><span class='w'>{pct(a['peso'], 0)}</span></li>" for a in members
    )
    stage_html.append(f"""
      <div class="stage" style="--c:var(--{CAMADAS[key][1]})">
        <div class="stage-head"><span class="stage-name">{name}</span><span class="stage-w">{pct(weight, 0)}</span></div>
        <div class="stage-bar"><span style="width:{weight / 0.40 * 100:.1f}%"></span></div>
        <p class="stage-desc">{desc}</p>
        <ul class="tickers">{chips}</ul>
      </div>""")
spec = [a for a in ativos if a["camada"] == "especulativo"]
spec_html = "".join(f"<li><span class='tk'>{a['ticker']}</span><span class='w'>{pct(a['peso'], 0)}</span></li>" for a in spec)

# ---------------------------------------------------------------- empresas
company_rows = []
for key, (label, s) in CAMADAS.items():
    members = [a for a in ativos if a["camada"] == key]
    company_rows.append(
        f"<tr class='group'><th colspan='4' scope='colgroup'><span class='dot' style='--c:var(--{s})'></span>{label} "
        f"<span class='muted'>· {pct(sum(a['peso'] for a in members), 0)} da carteira</span></th></tr>"
    )
    for a in members:
        company_rows.append(
            f"<tr><td><span class='tk'>{a['ticker']}</span><span class='co'>{esc(a['empresa'])}</span></td>"
            f"<td class='num'>{pct(a['peso'], 0)}</td><td class='txt'>{esc(a['papel'])}</td><td class='txt'>{esc(a['risco'])}</td></tr>"
        )

# ---------------------------------------------------------------- variantes
order = ["BH_EW", "BH_CAMADAS", "ATR_EW", "ATR_CAMADAS", "ATR_CAMADAS_VT", "SMH_BH", "QQQ_BH", "SPY_BH"]
labels = {
    "BH_EW": "Comprar e segurar, pesos iguais",
    "BH_CAMADAS": "Comprar e segurar, pesos por camada",
    "ATR_EW": "Momentum ATR, pesos iguais",
    "ATR_CAMADAS": "Momentum ATR, pesos por camada",
    "ATR_CAMADAS_VT": "Estratégia (ATR + camadas + trava de vol.)",
    "SMH_BH": "SMH, ETF de semicondutores",
    "QQQ_BH": "QQQ, Nasdaq-100",
    "SPY_BH": "SPY, S&P 500",
}
variant_rows = []
for k in order:
    r = V[k]
    cls = " class='hl'" if k == "ATR_CAMADAS_VT" else (" class='ref'" if k.endswith("_BH") and k not in ("BH_CAMADAS",) else "")
    variant_rows.append(
        f"<tr{cls}><th scope='row'>{labels[k]}</th>{signed(r['cagr'])}<td>{pct(r['volatilidade'], 0)}</td>"
        f"<td>{num(r['sharpe'])}</td>{dd(r['max_drawdown'])}<td>{num(r['calmar'])}</td>{signed(r['retorno_total'], 0)}</tr>"
    )

# ---------------------------------------------------------------- anos
annual_rows = []
cols = [c for c in D["annual"][0] if c not in ("ano", "Exposição média (principal)")]
for i, r in enumerate(D["annual"]):
    year = str(r["ano"])
    if i == 0:
        year += " <span class='muted'>desde fev</span>"
    if i == len(D["annual"]) - 1:
        year += " <span class='muted'>até 29/09</span>"
    cells = "".join(signed(r[c]) for c in cols)
    annual_rows.append(f"<tr><th scope='row'>{year}</th>{cells}<td>{pct(r['Exposição média (principal)'], 0)}</td></tr>")

# ---------------------------------------------------------------- sinal hoje
pos_rows = []
for a in ativos:
    r = positions[a["ticker"]]
    on = r["sinal"] == "comprado"
    state = "<span class='state on'>Comprado</span>" if on else "<span class='state off'>Em caixa</span>"
    stop = f"US$ {num(r['stop_atual'])}" if on else "—"
    gap = pct(r["distancia_stop"]) if on else "—"
    since = date_br(r["entrada"]) if on else "—"
    liq = r["liquidez_mediana_63d_usd"]
    liq_s = f"US$ {num(liq / 1e9, 1)} bi" if liq >= 1e9 else f"US$ {num(liq / 1e6, 1)} mi"
    pos_rows.append(
        f"<tr><th scope='row'><span class='dot' style='--c:var(--{CAMADAS[a['camada']][1]})'></span><span class='tk'>{a['ticker']}</span></th>"
        f"<td class='txt'>{state}</td><td>{since}</td><td>US$ {num(r['fechamento'])}</td>{signed(r['momentum_20d'])}"
        f"<td>{stop}</td><td>{gap}</td><td>{liq_s}</td><td>{pct(r['peso_alvo_vigente'])}</td></tr>"
    )

# ---------------------------------------------------------------- robustez
SUBL = {"ATR_CAMADAS_VT": "Estratégia", "BH_CAMADAS": "Cesta sem stops", "SMH_BH": "SMH", "QQQ_BH": "QQQ"}
sub = {(r["variante"], r["periodo"]): r for r in D["subperiods"]}
sub_rows = []
for k, lab in SUBL.items():
    a, b = sub[(k, "2020-2022")], sub[(k, "2023-2026")]
    sub_rows.append(
        f"<tr><th scope='row'>{lab}</th>{signed(a['cagr'])}<td>{num(a['sharpe'])}</td>{dd(a['max_drawdown'])}"
        f"{signed(b['cagr'])}<td>{num(b['sharpe'])}</td>{dd(b['max_drawdown'])}</tr>"
    )
STRESSL = {"base_15bps": "Base", "liquidez_reduzida": "Liquidez reduzida", "severo_50bps": "Severo"}
stress_rows = "".join(
    f"<tr><th scope='row'>{STRESSL.get(r['cenario'], r['cenario'])}</th><td>{pct(r['custo_por_ponta'], 2)}</td>"
    f"<td>{pct(r['slippage_stop'], 2)}</td>{signed(r['cagr'])}<td>{num(r['sharpe'])}</td>{dd(r['max_drawdown'])}</tr>"
    for r in D["stress"]
)
severe = D["stress"][-1]
loo = sorted(D["loo"], key=lambda r: r["sharpe"])
sh_max = max(r["sharpe"] for r in loo) * 1.08
loo_rows = "".join(
    f"<li><span class='tk'>sem {r['ativo_excluido']}</span>"
    f"<span class='lbar'><span style='width:{r['sharpe'] / sh_max * 100:.1f}%'></span><i style='left:{P['sharpe'] / sh_max * 100:.1f}%'></i></span>"
    f"<span class='lval'>{num(r['sharpe'])}</span><span class='lcagr'>{pct(r['cagr'], 1, True)}</span></li>"
    for r in loo
)

ep_text = ""
if ep:
    ep_text = (
        f"Na maior queda da cesta ({date_br(ep['pico'])} a {date_br(ep['vale'])}), a estratégia variou {pct(ep['estrategia_queda'], 1, True)} "
        f"enquanto a cesta caiu {pct(ep['cesta_queda'], 1)}. Nos 63 pregões seguintes, a estratégia subiu {pct(ep['estrategia_recuperacao'], 1, True)} "
        f"e a cesta {pct(ep['cesta_recuperacao'], 1, True)}."
    )

rel = sorted(D["annual"], key=lambda r: r[cols[0]] - r[cols[1]])[:2]
lag_text = " e ".join(
    f"{r['ano']} ({pct(r[cols[0]], 1, True)} contra {pct(r[cols[1]], 1, True)})" for r in sorted(rel, key=lambda r: r["ano"])
)

chart_data = json.dumps({"curves": D["curves"], "exposure": D["exposure"]}, ensure_ascii=False, separators=(",", ":"))

page = f"""<title>Tese Infraestrutura de IA</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,500..900&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;1,400&display=swap">
<style>
/* Layout: ficha técnica em coluna única. O topo mostra o caminho da energia, da usina ao chip; cada seção abaixo é uma faixa com tabela ou gráfico na largura da coluna. */
:root {{
  --bg: #f3f5f7;
  --surface: #ffffff;
  --sunk: #e9edf1;
  --ink: #0f141a;
  --ink-2: #445162;
  --muted: #748091;
  --line: #d8dee5;
  --accent: #1d5fb0;
  --up: #106b2c;
  --down: #b3261e;
  --s1: #2a78d6;
  --s2: #eb6834;
  --s3: #1baf7a;
  --s4: #eda100;
  --grid: #e3e7ec;
  --axis: #b9c2cc;
  --font-display: "Archivo", "Arial Narrow", "Helvetica Neue", Arial, sans-serif;
  --font-body: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
  --font-mono: "IBM Plex Mono", ui-monospace, "SFMono-Regular", Menlo, monospace;
  --step--1: 0.8125rem;
  --step-0: 1rem;
  --step-1: 1.25rem;
  --step-2: 1.75rem;
  --step-3: clamp(2.6rem, 7vw, 4.6rem);
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #0e1216; --surface: #151a20; --sunk: #1c232b; --ink: #edf1f5; --ink-2: #b3bdc9; --muted: #8591a0;
    --line: #29313b; --accent: #72a9ee; --up: #3fc46a; --down: #f07167;
    --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --grid: #222a33; --axis: #3a4450;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0e1216; --surface: #151a20; --sunk: #1c232b; --ink: #edf1f5; --ink-2: #b3bdc9; --muted: #8591a0;
  --line: #29313b; --accent: #72a9ee; --up: #3fc46a; --down: #f07167;
  --s1: #3987e5; --s2: #d95926; --s3: #199e70; --s4: #c98500; --grid: #222a33; --axis: #3a4450;
  color-scheme: dark;
}}
body {{ background: var(--bg); color: var(--ink); font-family: var(--font-body); font-size: var(--step-0); line-height: 1.55; }}
.page {{ max-width: 68rem; margin: 0 auto; padding-inline: max(16px, 4vw); padding-block: 2.5rem 4rem; display: grid; gap: 3.5rem; }}
h1, h2, h3 {{ font-family: var(--font-display); text-wrap: balance; margin: 0; }}
h2 {{ font-size: var(--step-2); font-weight: 800; font-stretch: 85%; letter-spacing: -0.01em; line-height: 1.1; }}
h3 {{ font-size: var(--step-1); font-weight: 700; font-stretch: 90%; }}
p {{ margin: 0; max-width: 68ch; }}
a {{ color: var(--accent); text-underline-offset: 2px; }}
.eyebrow {{ font-family: var(--font-mono); font-size: var(--step--1); text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink-2); }}
.muted {{ color: var(--muted); font-weight: 400; }}
.tk {{ font-family: var(--font-mono); font-weight: 500; letter-spacing: 0.02em; }}
section {{ display: grid; gap: 1.25rem; min-width: 0; }}
.lede {{ font-size: 1.0625rem; color: var(--ink-2); }}
.note {{ font-size: var(--step--1); color: var(--muted); max-width: 80ch; }}

/* hero */
.hero {{ display: grid; gap: 1.5rem; }}
.hero h1 {{ font-size: var(--step-3); font-weight: 900; font-stretch: 72%; line-height: 0.95; letter-spacing: -0.02em; text-transform: uppercase; }}
.hero .lede {{ font-size: 1.15rem; max-width: 60ch; }}
.path {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; border: 1px solid var(--line); background: var(--surface); border-radius: 6px; overflow: hidden; }}
.path-title {{ grid-column: 1 / -1; display: flex; justify-content: space-between; gap: 1rem; flex-wrap: wrap; padding: 0.75rem 1.25rem; border-bottom: 1px solid var(--line); background: var(--sunk); }}
.flow {{ font-family: var(--font-mono); font-size: var(--step--1); color: var(--ink-2); }}
.stage {{ padding: 1.1rem 1.25rem 1.25rem; display: grid; gap: 0.6rem; align-content: start; position: relative; min-width: 0; }}
.stage + .stage {{ border-left: 1px solid var(--line); }}
.stage + .stage::before {{ content: ""; position: absolute; left: -7px; top: 1.45rem; width: 12px; height: 12px; background: var(--surface); border-top: 1px solid var(--line); border-right: 1px solid var(--line); transform: rotate(45deg); }}
.stage-head {{ display: flex; justify-content: space-between; align-items: baseline; gap: 0.5rem; }}
.stage-name {{ font-family: var(--font-display); font-weight: 800; font-stretch: 80%; font-size: 1.3rem; text-transform: uppercase; letter-spacing: 0.01em; }}
.stage-w {{ font-family: var(--font-mono); font-size: 1.3rem; font-weight: 500; font-variant-numeric: tabular-nums; }}
.stage-bar {{ height: 6px; background: var(--sunk); border-radius: 3px; overflow: hidden; }}
.stage-bar span {{ display: block; height: 100%; background: var(--c); border-radius: 3px; }}
.stage-desc {{ font-size: var(--step--1); color: var(--ink-2); }}
.tickers {{ list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 0.4rem; }}
.tickers li {{ display: inline-flex; gap: 0.45rem; align-items: baseline; padding: 0.2rem 0.55rem; border: 1px solid var(--line); border-radius: 4px; font-size: 0.875rem; background: var(--bg); }}
.tickers .w {{ font-family: var(--font-mono); color: var(--muted); font-size: 0.8rem; }}
.satellites {{ grid-column: 1 / -1; display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem 1rem; padding: 0.85rem 1.25rem; border-top: 1px dashed var(--line); }}
.satellites .label {{ font-size: var(--step--1); color: var(--ink-2); flex: 1 1 18rem; min-width: 0; }}
.dot {{ display: inline-block; width: 0.6rem; height: 0.6rem; border-radius: 50%; background: var(--c); margin-right: 0.45rem; vertical-align: 0.05em; }}

.figures {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 2px solid var(--ink); }}
.figure {{ padding: 0.9rem 1rem 0 0; display: grid; gap: 0.2rem; align-content: start; min-width: 0; }}
.figure + .figure {{ padding-left: 1rem; border-left: 1px solid var(--line); }}
.figure b {{ font-family: var(--font-display); font-weight: 800; font-stretch: 80%; font-size: 2.1rem; line-height: 1; font-variant-numeric: tabular-nums; }}
.figure span {{ font-size: var(--step--1); color: var(--ink-2); }}
.verdict {{ display: grid; gap: 0.6rem; padding: 1.25rem 1.4rem; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; }}
.verdict .stance {{ font-family: var(--font-mono); font-size: var(--step--1); text-transform: uppercase; letter-spacing: 0.06em; color: var(--accent); }}

/* tabelas */
.table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; font-variant-numeric: tabular-nums; }}
th, td {{ padding: 0.6rem 0.8rem; text-align: right; border-bottom: 1px solid var(--line); vertical-align: top; white-space: nowrap; }}
thead th {{ font-family: var(--font-mono); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.06em; color: var(--ink-2); background: var(--sunk); }}
th:first-child, td:first-child {{ text-align: left; }}
tbody th {{ font-weight: 500; }}
tbody tr:last-child > * {{ border-bottom: 0; }}
td.txt {{ text-align: left; white-space: normal; min-width: 14rem; color: var(--ink-2); }}
td.num {{ text-align: right; }}
tr.group th {{ background: var(--bg); font-family: var(--font-display); font-weight: 700; font-stretch: 90%; font-size: 1rem; text-align: left; }}
tr.hl > * {{ background: color-mix(in srgb, var(--s1) 10%, var(--surface)); font-weight: 600; }}
tr.ref > * {{ color: var(--ink-2); }}
.co {{ display: block; font-size: 0.8rem; color: var(--muted); }}
td.up {{ color: var(--up); }}
td.down {{ color: var(--down); }}
.state {{ display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600; border: 1px solid; }}
.state.on {{ color: var(--up); border-color: color-mix(in srgb, var(--up) 45%, transparent); background: color-mix(in srgb, var(--up) 10%, transparent); }}
.state.off {{ color: var(--ink-2); border-color: var(--line); background: var(--sunk); }}

/* gráficos */
.chart {{ position: relative; background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 0.9rem 0.75rem 0.5rem; display: grid; gap: 0.5rem; min-width: 0; }}
.chart-head {{ display: flex; flex-wrap: wrap; justify-content: space-between; gap: 0.5rem 1.25rem; padding-inline: 0.35rem; }}
.chart-title {{ font-weight: 600; font-size: 0.95rem; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 0.35rem 1rem; font-size: var(--step--1); color: var(--ink-2); list-style: none; margin: 0; padding: 0; }}
.legend i {{ display: inline-block; width: 14px; height: 3px; border-radius: 2px; background: var(--c); margin-right: 0.4rem; vertical-align: 0.2em; }}
.legend.sq i {{ width: 10px; height: 10px; border-radius: 2px; vertical-align: -0.05em; }}
.plot {{ position: relative; }}
.plot svg {{ display: block; width: 100%; overflow: visible; }}
.plot svg text {{ fill: var(--muted); font-family: var(--font-mono); font-size: 11px; }}
.plot svg .endlabel {{ fill: var(--ink-2); font-family: var(--font-body); font-size: 12px; }}
.gridline {{ stroke: var(--grid); stroke-width: 1; }}
.baseline {{ stroke: var(--axis); stroke-width: 1; }}
.cross {{ stroke: var(--ink-2); stroke-width: 1; }}
.tip {{ position: absolute; top: 0; pointer-events: none; background: var(--surface); color: var(--ink); border: 1px solid var(--line); border-radius: 6px; padding: 0.5rem 0.65rem; font-size: 0.8rem; box-shadow: 0 6px 18px color-mix(in srgb, var(--ink) 14%, transparent); min-width: 11rem; z-index: 2; }}
.tip .t {{ font-family: var(--font-mono); color: var(--ink-2); margin-bottom: 0.25rem; }}
.tip .r {{ display: flex; justify-content: space-between; gap: 1rem; font-variant-numeric: tabular-nums; }}
.tip .r span:first-child::before {{ content: ""; display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: var(--c); margin-right: 0.4rem; }}
.tip .r.total {{ border-top: 1px solid var(--line); margin-top: 0.2rem; padding-top: 0.2rem; }}
.tip .r.total span:first-child::before {{ display: none; }}

.two {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 22rem), 1fr)); gap: 1rem; }}
.two > * {{ min-width: 0; }}
.stack {{ display: grid; gap: 1.75rem; }}
.stack > * {{ min-width: 0; }}
.choice {{ padding: 1.1rem 1.25rem; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); display: grid; gap: 0.5rem; align-content: start; }}
.choice .k {{ font-family: var(--font-mono); font-size: 0.8rem; color: var(--ink-2); text-transform: uppercase; letter-spacing: 0.06em; }}
.rules {{ display: grid; gap: 0; margin: 0; border-top: 1px solid var(--line); }}
.rules > div {{ display: grid; grid-template-columns: 13rem minmax(0, 1fr); gap: 1rem; padding: 0.85rem 0; border-bottom: 1px solid var(--line); }}
.rules dt {{ font-family: var(--font-display); font-weight: 700; font-stretch: 90%; font-size: 1.05rem; }}
.rules dd {{ margin: 0; color: var(--ink-2); max-width: 68ch; }}
.loo {{ list-style: none; margin: 0; padding: 0.75rem 1rem; display: grid; gap: 0.35rem; border: 1px solid var(--line); border-radius: 6px; background: var(--surface); }}
.loo li {{ display: grid; grid-template-columns: 5.5rem minmax(0, 1fr) 2.8rem 3.6rem; align-items: center; gap: 0.6rem; font-size: 0.85rem; font-variant-numeric: tabular-nums; }}
.lbar {{ position: relative; height: 10px; background: var(--sunk); border-radius: 3px; }}
.lbar span {{ position: absolute; inset: 0 auto 0 0; background: var(--s1); border-radius: 3px; }}
.lbar i {{ position: absolute; top: -3px; bottom: -3px; width: 2px; background: var(--ink); }}
.lval {{ text-align: right; font-family: var(--font-mono); }}
.lcagr {{ text-align: right; color: var(--muted); font-family: var(--font-mono); font-size: 0.8rem; }}
.risks {{ margin: 0; padding-left: 1.1rem; display: grid; gap: 0.6rem; color: var(--ink-2); }}
.risks b {{ color: var(--ink); }}
.warning {{ padding: 1rem 1.25rem; border-left: 4px solid var(--s4); background: var(--surface); border-radius: 0 6px 6px 0; }}
footer {{ border-top: 1px solid var(--line); padding-top: 1.25rem; display: grid; gap: 0.5rem; font-size: var(--step--1); color: var(--muted); }}
footer code {{ font-family: var(--font-mono); font-size: 0.8rem; color: var(--ink-2); }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}

@media (max-width: 760px) {{
  .path {{ grid-template-columns: minmax(0, 1fr); }}
  .stage + .stage {{ border-left: 0; border-top: 1px solid var(--line); }}
  .stage + .stage::before {{ left: 1.6rem; top: -7px; transform: rotate(135deg); }}
  .figures {{ grid-template-columns: repeat(2, minmax(0, 1fr)); row-gap: 1rem; }}
  .figure:nth-child(3) {{ padding-left: 0; border-left: 0; }}
  .rules > div {{ grid-template-columns: minmax(0, 1fr); gap: 0.25rem; }}
}}
</style>

<main class="page">
  <header class="hero">
    <p class="eyebrow">Tese de investimento · 12 ações americanas · preços até 29/09/2026</p>
    <h1>Infraestrutura de IA</h1>
    <p class="lede">A demanda por IA não termina na GPU. Cada cluster novo precisa de memória, servidores, energia ininterrupta, refrigeração,
    conexão à rede elétrica e geração dedicada. A tese compra essa cadeia física inteira, com peso maior onde a ligação com a IA é direta
    e a empresa é grande e líquida.</p>

    <div class="path" role="group" aria-label="Pesos da carteira por etapa, da geração de energia aos chips">
      <div class="path-title"><span class="eyebrow">Da usina ao chip</span><span class="flow">energia → rede → data center → rack → GPU</span></div>
      {''.join(stage_html)}
      <div class="satellites">
        <span class="stage-name" style="font-size:1rem"><span class="dot" style="--c:var(--s4)"></span>Satélites {pct(sum(a['peso'] for a in spec), 0)}</span>
        <ul class="tickers">{spec_html}</ul>
        <span class="label">Apostas pequenas em pivôs para data centers de IA (DGXX, VIVO) e em infraestrutura espacial (RDW), onde a ligação com a IA ainda é indireta.</span>
      </div>
    </div>

    <div class="figures">
      <div class="figure"><b>{pct(P['cagr'], 1, True)}</b><span>ao ano, fev/2020 a set/2026</span></div>
      <div class="figure"><b>{num(P['sharpe'])}</b><span>Sharpe; QQQ teve {num(QQQ['sharpe'])}</span></div>
      <div class="figure"><b>{pct(P['max_drawdown'])}</b><span>maior queda; a cesta sem stops caiu {pct(BH['max_drawdown'])}</span></div>
      <div class="figure"><b>{pct(st['exposicao_atual_mercado'], 0)}</b><span>investido hoje; {n_long} de 12 sinais comprados</span></div>
    </div>

    <div class="verdict">
      <span class="stance">Postura: satélite com controle de risco · não aprovada para capital real</span>
      <p>A estratégia teria rendido {pct(P['cagr'], 1)} ao ano com queda máxima de {pct(P['max_drawdown'])}. Comprar a mesma cesta e segurar rendeu
      {pct(BH['cagr'], 1)} ao ano, mas com quedas de até {pct(BH['max_drawdown'])}. Os stops cortaram a pior queda pela metade e, em troca, deixaram
      {num((BH['cagr'] - P['cagr']) * 100, 1)} pontos percentuais de retorno anual na mesa, num período em que quase todas essas ações dispararam.
      Ajustado ao risco, o resultado ficou perto do QQQ. Como a lista foi escolhida depois da alta da IA, o histórico superestima o que se ganharia
      escolhendo essas ações em 2020.</p>
    </div>
  </header>

  <section aria-labelledby="empresas">
    <h2 id="empresas">As 12 empresas e o papel de cada uma</h2>
    <p class="lede">NVDA, MU, SMCI e VRT vendem direto para data centers de IA. PWR, GEV, VST e BE dependem da carga elétrica que esses data centers criam.
    STM e RDW têm exposição indireta. DGXX e VIVO ainda estão executando a mudança de negócio. Os pesos seguem essa ordem de proximidade.</p>
    <div class="table-wrap"><table>
      <thead><tr><th scope="col">Empresa</th><th scope="col">Peso</th><th scope="col" style="text-align:left">Papel na tese</th><th scope="col" style="text-align:left">Principal risco</th></tr></thead>
      <tbody>{''.join(company_rows)}</tbody>
    </table></div>
  </section>

  <section aria-labelledby="regras">
    <h2 id="regras">Regras da carteira</h2>
    <p class="lede">Definidas antes do backtest e sem otimização de parâmetros. Todo sinal é calculado no fechamento e executado no pregão seguinte, com custo de 0,15% por lado.</p>
    <dl class="rules">
      <div><dt>Entrada e saída</dt><dd>Compra quando o retorno de 20 pregões vira positivo. Sai quando ele fica negativo ou quando o preço toca o stop de 2,5 vezes o ATR de 14 dias, que só sobe. Se a ação abrir abaixo do stop, a venda sai na abertura.</dd></div>
      <div><dt>Pesos por camada</dt><dd>Chips e computação 40%, infraestrutura do data center 22%, geração de energia 28% e satélites 10%. Cada ação tem sua parcela; quando o sinal está fora, a parcela fica em caixa.</dd></div>
      <div><dt>Filtro de liquidez</dt><dd>Só entra quem negocia pelo menos US$ 5 milhões por dia (mediana de 63 pregões). O peso de quem não passa vai para as outras ações da mesma camada. Por isso GE Vernova só entra em 2024 e VivoPower fica de fora na maior parte do tempo.</dd></div>
      <div><dt>Rebalanceamento</dt><dd>Mensal. A decisão usa o último pregão do mês e a execução acontece no pregão seguinte.</dd></div>
      <div><dt>Trava de volatilidade</dt><dd>Se a volatilidade de 63 pregões passar de 25% ao ano, a exposição total cai na mesma proporção, sem alavancagem. Na prática quase não atua (multiplicador médio de {num(st['multiplicador_vol_medio'])}), porque os stops já mantêm a volatilidade perto de 20%.</dd></div>
    </dl>
  </section>

  <section aria-labelledby="resultado">
    <h2 id="resultado">Resultado de fev/2020 a set/2026</h2>
    <div class="chart" id="nav-chart">
      <div class="chart-head"><span class="chart-title">Patrimônio, base 100 (escala log)</span>
        <ul class="legend">
          <li style="--c:var(--s1)"><i></i>Estratégia</li><li style="--c:var(--s2)"><i></i>Cesta sem stops</li>
          <li style="--c:var(--s3)"><i></i>SMH</li><li style="--c:var(--s4)"><i></i>QQQ</li></ul></div>
      <div class="plot" data-kind="nav"></div>
    </div>
    <div class="chart" id="dd-chart">
      <div class="chart-head"><span class="chart-title">Queda desde o pico (%)</span></div>
      <div class="plot" data-kind="dd"></div>
    </div>
    <div class="table-wrap"><table>
      <thead><tr><th scope="col">Carteira</th><th scope="col">Ao ano</th><th scope="col">Vol.</th><th scope="col">Sharpe</th><th scope="col">Maior queda</th><th scope="col">Calmar</th><th scope="col">Acumulado</th></tr></thead>
      <tbody>{''.join(variant_rows)}</tbody>
    </table></div>
    <p class="note">Cinco variantes foram testadas. Considerando essas tentativas, a chance de o Sharpe de {num(P['sharpe'])} ter vindo só de sorte é baixa
    (Deflated Sharpe de {num(st['dsr_5_tentativas'], 3)}), mas a probabilidade de ele superar de fato o Sharpe do QQQ é de {num(st['psr_vs_qqq'], 2)}. Sharpe com taxa livre de risco zero; comprar e segurar sem dividendos.</p>
    <div class="two">
      <div class="choice"><span class="k">Com stops (a estratégia)</span><h3>Quedas parecidas com as do índice</h3>
        <p>Ficou em média {pct(st['exposicao_media_mercado'], 0)} investida, com volatilidade de {pct(P['volatilidade'], 0)} ao ano. O custo é perder parte das altas.</p></div>
      <div class="choice"><span class="k">Sem stops (comprar e segurar)</span><h3>Toda a alta, e toda a queda</h3>
        <p>Volatilidade de {pct(BH['volatilidade'], 0)} ao ano e quedas de até {pct(BH['max_drawdown'])}. Só cabe como posição pequena, que você aguente ver cair pela metade.</p></div>
    </div>
  </section>

  <section aria-labelledby="atras">
    <h2 id="atras">Quando a estratégia fica para trás</h2>
    <p class="lede">Os anos de maior distância para a cesta sem stops foram {lag_text}. {ep_text} Os stops protegem na queda, e a recompra só acontece
    depois que o retorno de 20 pregões volta a ficar positivo, o que deixa parte da recuperação para trás.</p>
    <div class="table-wrap"><table>
      <thead><tr><th scope="col">Ano</th><th scope="col">Estratégia</th><th scope="col">Cesta sem stops</th><th scope="col">SMH</th><th scope="col">QQQ</th><th scope="col">Investido (média)</th></tr></thead>
      <tbody>{''.join(annual_rows)}</tbody>
    </table></div>
    <div class="chart" id="exp-chart">
      <div class="chart-head"><span class="chart-title">Quanto do patrimônio esteve investido, por camada (média do mês)</span>
        <ul class="legend sq">
          <li style="--c:var(--s1)"><i></i>Chips e computação</li><li style="--c:var(--s2)"><i></i>Infraestrutura do data center</li>
          <li style="--c:var(--s3)"><i></i>Geração de energia</li><li style="--c:var(--s4)"><i></i>Satélites</li></ul></div>
      <div class="plot" data-kind="exp"></div>
    </div>
  </section>

  <section aria-labelledby="hoje">
    <h2 id="hoje">Sinal no fechamento de 29/09/2026</h2>
    <p class="lede">{n_long} das 12 ações estão com sinal de compra e {pct(st['exposicao_atual_mercado'], 0)} do patrimônio está investido. O próximo rebalanceamento usa o fechamento de 30/09.</p>
    <div class="table-wrap"><table>
      <thead><tr><th scope="col">Ação</th><th scope="col" style="text-align:left">Sinal</th><th scope="col">Desde</th><th scope="col">Fechamento</th><th scope="col">Retorno 20d</th><th scope="col">Stop</th><th scope="col">Folga</th><th scope="col">Liquidez/dia</th><th scope="col">Peso</th></tr></thead>
      <tbody>{''.join(pos_rows)}</tbody>
    </table></div>
    <p class="note">Stops são níveis da simulação. Uma abertura em gap pode executar abaixo deles. Isto é o estado de um modelo em simulação, não uma ordem nem recomendação individual.</p>
  </section>

  <section aria-labelledby="robustez">
    <h2 id="robustez">Quanto o resultado aguenta</h2>
    <div class="stack">
      <div style="display:grid;gap:0.75rem">
        <h3>Antes e depois do ChatGPT</h3>
        <div class="table-wrap"><table>
          <thead><tr><th scope="col" rowspan="2">Carteira</th><th scope="colgroup" colspan="3" style="text-align:center">2020–2022</th><th scope="colgroup" colspan="3" style="text-align:center">2023–2026</th></tr>
          <tr><th scope="col">Ao ano</th><th scope="col">Sharpe</th><th scope="col">Queda</th><th scope="col">Ao ano</th><th scope="col">Sharpe</th><th scope="col">Queda</th></tr></thead>
          <tbody>{''.join(sub_rows)}</tbody>
        </table></div>
        <p class="note">O primeiro período inclui o crash de 2020 e o bear market de semicondutores de 2022.</p>
      </div>
      <div style="display:grid;gap:0.75rem">
        <h3>Custo de execução mais alto</h3>
        <div class="table-wrap"><table>
          <thead><tr><th scope="col">Cenário</th><th scope="col">Custo/lado</th><th scope="col">Deslize no stop</th><th scope="col">Ao ano</th><th scope="col">Sharpe</th><th scope="col">Queda</th></tr></thead>
          <tbody>{stress_rows}</tbody>
        </table></div>
        <p class="note">A estratégia opera bastante. Com 0,50% por lado, o retorno cai para {pct(severe['cagr'], 1, True)} ao ano.</p>
      </div>
    </div>
    <div style="display:grid;gap:0.75rem">
      <h3>Tirando uma ação por vez</h3>
      <p class="lede">O Sharpe varia de {num(loo[0]['sharpe'])} (sem {loo[0]['ativo_excluido']}) a {num(loo[-1]['sharpe'])} (sem {loo[-1]['ativo_excluido']}). A NVIDIA é a única peça cuja ausência muda o resultado de forma relevante. A linha escura marca o Sharpe da carteira completa ({num(P['sharpe'])}); o número cinza é o retorno ao ano.</p>
      <ul class="loo">{loo_rows}</ul>
    </div>
    <div class="warning"><strong>Viés de seleção.</strong> A lista foi escolhida em setembro de 2026, quando já se sabia quais empresas ganharam com a IA.
    Vistra, Vertiv, GE Vernova, Bloom e NVIDIA estão entre as maiores altas do mercado americano no período. Nenhum teste desta página remove esse efeito.
    O backtest mostra como as regras de risco teriam se comportado nesta cesta, não quanto se ganharia escolhendo ações de IA em 2020.</div>
  </section>

  <section aria-labelledby="riscos">
    <h2 id="riscos">O que derruba a tese</h2>
    <ul class="risks">
      <li><b>Um fator só.</b> Todas as camadas dependem do investimento em IA dos hiperescaladores. Um corte nesse investimento derruba chips, data center e energia ao mesmo tempo. A correlação média entre as ações foi {num(st['correlacao_media_pares'])}.</li>
      <li><b>Preço.</b> Vários nomes já negociam a múltiplos que pressupõem anos de crescimento. Uma decepção de guidance pode abrir um gap maior que qualquer stop.</li>
      <li><b>Política e regulação.</b> Controles de exportação de chips, tarifas, licenças de geração, conexão à rede e regras para data centers ao lado de usinas nucleares.</li>
      <li><b>Eficiência.</b> Modelos e chips mais eficientes podem reduzir a energia e o hardware necessários por unidade de computação.</li>
      <li><b>Microcaps.</b> DGXX e VIVO tiveram liquidez mínima em boa parte da amostra, e a VivoPower já mudou de negócio várias vezes. O filtro de liquidez as mantém fora nesses períodos, mas a execução real nelas tende a custar mais que 0,15%.</li>
      <li><b>Investidor no Brasil.</b> Câmbio, tributação e, se for via BDR, paridade e liquidez do BDR. Confirme cada programa na B3 antes de operar.</li>
    </ul>
  </section>

  <footer>
    <p>Gerado por <code>scripts/run_tese_ia_infraestrutura.py</code> no repositório iitauquant, com preços diários do Yahoo Finance congelados em 29/09/2026 (ajustados por desdobramentos, sem dividendos).
    A VivoPower negociava como VVPR até 16/03/2026, quando passou a VIVO. Dados de negócio são descrições qualitativas; confirme nos arquivamentos de cada empresa na SEC.</p>
    <p>Simulação histórica sem ordens reais. Pesquisa educacional, não é recomendação individual de investimento.</p>
  </footer>
</main>

<script type="application/json" id="chart-data">{chart_data}</script>
<script>
(() => {{
  const D = JSON.parse(document.getElementById('chart-data').textContent);
  const NS = 'http://www.w3.org/2000/svg';
  const br = (v, d = 1) => v.toLocaleString('pt-BR', {{ minimumFractionDigits: d, maximumFractionDigits: d }});
  const MONTHS = ['jan','fev','mar','abr','mai','jun','jul','ago','set','out','nov','dez'];
  const dBR = s => `${{s.slice(8, 10)}}/${{s.slice(5, 7)}}/${{s.slice(0, 4)}}`;
  const mBR = s => `${{MONTHS[+s.slice(5, 7) - 1]}}/${{s.slice(0, 4)}}`;
  const LINES = [
    {{ key: 'principal', label: 'Estratégia', c: 's1', w: 2.4 }},
    {{ key: 'bh', label: 'Cesta sem stops', c: 's2', w: 1.6 }},
    {{ key: 'smh', label: 'SMH', c: 's3', w: 1.6 }},
    {{ key: 'qqq', label: 'QQQ', c: 's4', w: 1.6 }},
  ];
  const LAYERS = [
    {{ key: 'computacao', label: 'Chips e computação', c: 's1' }},
    {{ key: 'infraestrutura', label: 'Infra do data center', c: 's2' }},
    {{ key: 'energia', label: 'Geração de energia', c: 's3' }},
    {{ key: 'especulativo', label: 'Satélites', c: 's4' }},
  ];
  const el = (tag, attrs = {{}}, parent) => {{
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }};
  const years = (labels, parse) => {{
    const out = [];
    labels.forEach((s, i) => {{ if (i === 0 || parse(s) !== parse(labels[i - 1])) out.push([i, parse(s)]); }});
    return out;
  }};

  function placeTip(plot, tip, x, width) {{
    tip.hidden = false;
    const tw = tip.offsetWidth;
    let left = x + 14;
    if (left + tw > width) left = x - tw - 14;
    tip.style.left = Math.max(0, left) + 'px';
  }}

  function lineChart(plot, kind) {{
    const C = D.curves;
    const n = C.dates.length;
    const values = kind === 'nav' ? C.nav : C.dd;
    const tip = document.createElement('div');
    tip.className = 'tip'; tip.hidden = true; plot.appendChild(tip);
    let svg;
    function render() {{
      const W = plot.clientWidth;
      const H = kind === 'nav' ? Math.max(240, Math.min(380, W * 0.5)) : Math.max(150, Math.min(210, W * 0.28));
      const wide = W > 560, endLabels = kind === 'nav' && wide;
      const m = {{ l: 46, r: wide ? 132 : 10, t: 8, b: 24 }};
      const pw = W - m.l - m.r, ph = H - m.t - m.b;
      if (svg) svg.remove();
      svg = el('svg', {{ viewBox: `0 0 ${{W}} ${{H}}`, height: H, role: 'img',
        'aria-label': kind === 'nav' ? 'Patrimônio da estratégia, da cesta sem stops, do SMH e do QQQ, base 100' : 'Queda desde o pico das quatro carteiras' }});
      plot.insertBefore(svg, tip);
      const all = LINES.flatMap(s => values[s.key]);
      let y, ticks;
      if (kind === 'nav') {{
        const lo = Math.log10(Math.min(...all) * 0.92), hi = Math.log10(Math.max(...all) * 1.08);
        y = v => m.t + ph - (Math.log10(v) - lo) / (hi - lo) * ph;
        ticks = [50, 100, 200, 500, 1000, 2000, 5000].filter(t => Math.log10(t) >= lo && Math.log10(t) <= hi);
      }} else {{
        const lo = Math.floor(Math.min(...all) / 10) * 10;
        y = v => m.t + (0 - v) / (0 - lo) * ph;
        ticks = []; for (let t = 0; t >= lo; t -= 10) ticks.push(t);
      }}
      const x = i => m.l + i / (n - 1) * pw;
      ticks.forEach(t => {{
        el('line', {{ x1: m.l, x2: m.l + pw, y1: y(t), y2: y(t), class: t === 0 && kind === 'dd' ? 'baseline' : 'gridline' }}, svg);
        const tx = el('text', {{ x: m.l - 8, y: y(t) + 4, 'text-anchor': 'end' }}, svg);
        tx.textContent = kind === 'nav' ? t.toLocaleString('pt-BR') : (t === 0 ? '0' : '−' + Math.abs(t));
      }});
      el('line', {{ x1: m.l, x2: m.l + pw, y1: m.t + ph, y2: m.t + ph, class: 'baseline' }}, svg);
      years(C.dates, s => s.slice(0, 4)).forEach(([i, yr], k) => {{
        if (k === 0 && i === 0 && C.dates[0].slice(5, 7) !== '01') return;
        const tx = el('text', {{ x: x(i), y: H - 6, 'text-anchor': 'middle' }}, svg); tx.textContent = yr;
        el('line', {{ x1: x(i), x2: x(i), y1: m.t + ph, y2: m.t + ph + 4, class: 'baseline' }}, svg);
      }});
      [...LINES].reverse().forEach(s => {{
        const d = values[s.key].map((v, i) => `${{i ? 'L' : 'M'}}${{x(i).toFixed(1)}},${{y(v).toFixed(1)}}`).join('');
        el('path', {{ d, fill: 'none', style: `stroke:var(--${{s.c}})`, 'stroke-width': s.w, 'stroke-linejoin': 'round' }}, svg);
      }});
      if (endLabels) {{
        const ends = LINES.map(s => ({{ s, v: values[s.key][n - 1], y: y(values[s.key][n - 1]) }})).sort((a, b) => a.y - b.y);
        for (let k = 1; k < ends.length; k++) ends[k].y = Math.max(ends[k].y, ends[k - 1].y + 15);
        ends.forEach(e => {{
          const tx = el('text', {{ x: m.l + pw + 8, y: e.y + 4, class: 'endlabel' }}, svg);
          tx.textContent = `${{e.s.label}} ${{Math.round(e.v).toLocaleString('pt-BR')}}`;
        }});
      }}
      const cross = el('line', {{ y1: m.t, y2: m.t + ph, class: 'cross', visibility: 'hidden' }}, svg);
      const dots = LINES.map(s => el('circle', {{ r: 4, style: `fill:var(--${{s.c}});stroke:var(--surface)`, 'stroke-width': 2, visibility: 'hidden' }}, svg));
      const hit = el('rect', {{ x: m.l, y: m.t, width: pw, height: ph, fill: 'transparent' }}, svg);
      const show = evt => {{
        const r = svg.getBoundingClientRect();
        const i = Math.max(0, Math.min(n - 1, Math.round((evt.clientX - r.left - m.l) / pw * (n - 1))));
        cross.setAttribute('x1', x(i)); cross.setAttribute('x2', x(i)); cross.setAttribute('visibility', 'visible');
        LINES.forEach((s, k) => {{ dots[k].setAttribute('cx', x(i)); dots[k].setAttribute('cy', y(values[s.key][i])); dots[k].setAttribute('visibility', 'visible'); }});
        tip.innerHTML = `<div class="t">semana de ${{dBR(C.dates[i])}}</div>` + LINES.map(s =>
          `<div class="r" style="--c:var(--${{s.c}})"><span>${{s.label}}</span><span>${{kind === 'nav' ? br(values[s.key][i], 0) : br(values[s.key][i], 1) + '%'}}</span></div>`).join('');
        placeTip(plot, tip, x(i), W);
      }};
      const hide = () => {{ tip.hidden = true; cross.setAttribute('visibility', 'hidden'); dots.forEach(d => d.setAttribute('visibility', 'hidden')); }};
      hit.addEventListener('pointermove', show); hit.addEventListener('pointerdown', show); hit.addEventListener('pointerleave', hide);
    }}
    new ResizeObserver(render).observe(plot);
  }}

  function exposureChart(plot) {{
    const E = D.exposure;
    const n = E.months.length;
    const tip = document.createElement('div');
    tip.className = 'tip'; tip.hidden = true; plot.appendChild(tip);
    let svg;
    function render() {{
      const W = plot.clientWidth;
      const H = Math.max(200, Math.min(300, W * 0.36));
      const m = {{ l: 40, r: 8, t: 8, b: 24 }};
      const pw = W - m.l - m.r, ph = H - m.t - m.b;
      if (svg) svg.remove();
      svg = el('svg', {{ viewBox: `0 0 ${{W}} ${{H}}`, height: H, role: 'img', 'aria-label': 'Percentual do patrimônio investido por camada, média de cada mês' }});
      plot.insertBefore(svg, tip);
      const y = v => m.t + ph - v / 100 * ph;
      [0, 25, 50, 75, 100].forEach(t => {{
        el('line', {{ x1: m.l, x2: m.l + pw, y1: y(t), y2: y(t), class: t === 0 ? 'baseline' : 'gridline' }}, svg);
        const tx = el('text', {{ x: m.l - 8, y: y(t) + 4, 'text-anchor': 'end' }}, svg); tx.textContent = t + '%';
      }});
      const slot = pw / n, gap = slot > 6 ? 1.5 : 0.8, bw = Math.max(1, slot - gap);
      years(E.months, s => s.slice(0, 4)).forEach(([i, yr]) => {{
        if (i === 0 && E.months[0].slice(5, 7) !== '01') return;
        const tx = el('text', {{ x: m.l + i * slot, y: H - 6, 'text-anchor': 'middle' }}, svg); tx.textContent = yr;
      }});
      const groups = [];
      E.months.forEach((mo, i) => {{
        const g = el('g', {{}}, svg);
        let acc = 0;
        LAYERS.forEach(L => {{
          const v = E.layers[L.key][i];
          if (v > 0.05) {{
            const top = y(acc + v), h = y(acc) - top;
            el('rect', {{ x: m.l + i * slot + gap / 2, y: top + (acc > 0 ? 0.75 : 0), width: bw, height: Math.max(0, h - (acc > 0 ? 0.75 : 0)), style: `fill:var(--${{L.c}})`, rx: h > 3 ? 1 : 0 }}, g);
          }}
          acc += v;
        }});
        groups.push(g);
      }});
      const hit = el('rect', {{ x: m.l, y: m.t, width: pw, height: ph, fill: 'transparent' }}, svg);
      const show = evt => {{
        const r = svg.getBoundingClientRect();
        const i = Math.max(0, Math.min(n - 1, Math.floor((evt.clientX - r.left - m.l) / slot)));
        groups.forEach((g, k) => g.style.opacity = k === i ? 1 : 0.45);
        const total = LAYERS.reduce((s, L) => s + E.layers[L.key][i], 0);
        tip.innerHTML = `<div class="t">${{mBR(E.months[i])}}</div>` + [...LAYERS].reverse().map(L =>
          `<div class="r" style="--c:var(--${{L.c}})"><span>${{L.label}}</span><span>${{br(E.layers[L.key][i], 0)}}%</span></div>`).join('') +
          `<div class="r total"><span>Investido</span><span>${{br(total, 0)}}%</span></div><div class="r total"><span>Caixa</span><span>${{br(100 - total, 0)}}%</span></div>`;
        placeTip(plot, tip, m.l + (i + 0.5) * slot, W);
      }};
      const hide = () => {{ tip.hidden = true; groups.forEach(g => g.style.opacity = 1); }};
      hit.addEventListener('pointermove', show); hit.addEventListener('pointerdown', show); hit.addEventListener('pointerleave', hide);
    }}
    new ResizeObserver(render).observe(plot);
  }}

  document.querySelectorAll('.plot').forEach(p => {{
    if (p.dataset.kind === 'exp') exposureChart(p); else lineChart(p, p.dataset.kind);
  }});
}})();
</script>
"""


# Esqueleto de documento: a página acima só contém head (title/fontes/estilo) e body (main/scripts).
split = page.index('<main class="page">')
document = (
    '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    "<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
    + page[:split]
    + "</head>\n<body>\n"
    + page[split:]
    + "\n</body>\n</html>\n"
)
OUT.write_text(document, encoding="utf-8")
print(f"Relatório gerado: {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")
