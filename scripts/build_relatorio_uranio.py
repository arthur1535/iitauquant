"""Gera relatorios/cadeia_uranio_analise_<data>.html a partir de results/uranium_research/."""

from __future__ import annotations

import base64
import html
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "results" / "uranium_research"
CHARTS = RESEARCH / "graficos"
PRIMARY = ["U-UN.TO", "LEU", "PDN.AX", "CCJ"]


def load() -> dict:
    manifest = json.loads((RESEARCH / "manifesto_uranio.json").read_text(encoding="utf-8"))
    return {
        "manifest": manifest,
        "metrics": pd.read_csv(RESEARCH / "uranio_metricas_comparativas.csv").set_index("ticker"),
        "periods": pd.read_csv(RESEARCH / "uranio_metricas_por_periodo.csv"),
        "stress": pd.read_csv(RESEARCH / "uranio_stress.csv"),
        "dsr": pd.read_csv(RESEARCH / "uranio_dsr.csv").set_index("ticker"),
        "corr": pd.read_csv(RESEARCH / "uranio_correlacao.csv", index_col=0),
        "beta": pd.read_csv(RESEARCH / "uranio_beta.csv").set_index("ticker"),
        "liq": pd.read_csv(RESEARCH / "uranio_liquidez.csv").set_index("ticker"),
        "fund": json.loads((RESEARCH / "uranio_fundamentos_snapshot.json").read_text(encoding="utf-8")),
        "last": {
            t: pd.read_csv(RESEARCH / f"{t}_equity.csv", index_col=0, parse_dates=True).iloc[-1]
            for t in manifest["ativos"]
        },
    }


def img(name: str, alt: str) -> str:
    data = base64.b64encode((CHARTS / name).read_bytes()).decode("ascii")
    return f'<figure><img src="data:image/png;base64,{data}" alt="{html.escape(alt)}"><figcaption>{html.escape(alt)}</figcaption></figure>'


def pct(value: float, digits: int = 1) -> str:
    return f"{value:+.{digits}f}%".replace(".", ",")


def share(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%".replace(".", ",")


def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def money(value: float | None, currency: str) -> str:
    if value is None or pd.isna(value):
        return "n/d"
    for size, suffix in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(value) >= size:
            return f"{currency} {value / size:,.2f} {suffix}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{currency} {value:,.0f}"


def table(headers: list[str], rows: list[list[str]], cls: str = "") -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<div class="scroll"><table class="{cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def label(ticker: str, manifest: dict) -> str:
    return html.escape(manifest["ativos"][ticker]["listagem"])


def fundamentals_rows(fund: dict, manifest: dict) -> list[list[str]]:
    rows = []
    for ticker in PRIMARY:
        entry = fund["ativos"].get(ticker, {})
        snap = entry.get("snapshot", {})
        dre = entry.get("dre_anual", {})
        revenue = {k: v for k, v in dre.get("Total Revenue", {}).items() if v is not None}
        gross = dre.get("Gross Profit", {})
        operating = dre.get("Operating Income", {})
        net = dre.get("Net Income", {})
        fin_ccy = snap.get("financialCurrency") or snap.get("currency") or ""
        quote_ccy = snap.get("currency") or ""
        years = sorted(revenue)
        if years and revenue[years[-1]]:
            last = years[-1]
            rev = revenue[last]
            growth = pct((rev / revenue[years[-2]] - 1) * 100) if len(years) > 1 and revenue[years[-2]] else "n/d"
            gm = pct(gross[last] / rev * 100) if gross.get(last) is not None else "n/d"
            om = pct(operating[last] / rev * 100) if operating.get(last) is not None else "n/d"
            rows.append([
                label(ticker, manifest), last, money(rev, fin_ccy), growth, gm, om,
                money(net.get(last), fin_ccy), money(snap.get("marketCap"), quote_ccy),
            ])
        else:
            rows.append([
                label(ticker, manifest), max(net) if net else "n/d", "sem receita operacional", "—", "—", "—",
                money(net.get(max(net)) if net else None, quote_ccy) + "<br><small>(marcação a mercado do urânio)</small>",
                money(snap.get("marketCap"), quote_ccy),
            ])
    return rows


def build() -> str:
    d = load()
    m, mf = d["metrics"], d["manifest"]
    per, st, dsr = d["periods"], d["stress"], d["dsr"]
    bars = {a["ticker"]: a["ultima_barra"] for a in mf["dados"]}
    last_bar = f'{bars["SPY"]} (EUA/Canadá) e {bars["PDN.AX"]} (ASX)'

    lines = [t for t in mf["ativos"] if t not in ("URA", "SPY")]
    in_position = [t for t in lines if int(d["last"][t]["position"]) == 1]
    signal_text = (
        f"as {len(lines)} linhas estão <em>fora de posição</em> no Momentum ATR (momentum de 20 pregões abaixo de zero ou stop acionado)."
        if not in_position
        else f"{len(in_position)} de {len(lines)} linhas estão compradas no Momentum ATR: {', '.join(label(t, mf) for t in in_position)}."
    )
    bh_wins = sum(m.loc[t, "bh_sharpe"] > m.loc[t, "mom_sharpe"] for t in lines)
    dsr_max = dsr["dsr_probabilidade"].max()

    perf_rows = []
    for t in mf["ativos"]:
        r = m.loc[t]
        perf_rows.append([
            label(t, mf), r["moeda"], str(int(r["barras"])), str(int(r["operacoes"])),
            pct(r["mom_retorno_total_pct"]), num(r["mom_sharpe"]), pct(r["mom_max_dd_pct"]),
            pct(r["bh_retorno_total_pct"]), num(r["bh_sharpe"]), pct(r["bh_max_dd_pct"]),
            share(r["exposicao_pct"], 0),
        ])

    period_rows = []
    for _, r in per[per["ticker"].isin(PRIMARY + ["URA", "SPY"])].iterrows():
        period_rows.append([
            label(r["ticker"], mf), r["periodo"], r["primeira_barra"],
            pct(r["mom_retorno_total_pct"]), num(r["mom_sharpe"]),
            pct(r["bh_retorno_total_pct"]), num(r["bh_sharpe"]),
        ])

    stress_rows = []
    for t in lines:
        s = st[st["ticker"] == t].set_index("scenario")
        stress_rows.append([label(t, mf)] + [
            f'{pct(s.loc[sc, "total_return"] * 100)} <small>(Sharpe {num(s.loc[sc, "sharpe_ratio"])})</small>'
            for sc in ("base_15bps", "liquidez_reduzida", "severo_50bps")
        ])

    dsr_rows = [[label(t, mf), num(r["sharpe_observado"], 3), num(r["sharpe_benchmark_multiplos_testes"], 3), num(r["dsr_probabilidade"], 3)] for t, r in dsr.iterrows()]

    beta_rows = [[html.escape(t), num(r["beta_URA"]), num(r["beta_SPY"]), share(r["vol_anual_pct"])] for t, r in d["beta"].iterrows()]

    liq_rows = []
    for t, r in d["liq"].iterrows():
        audit = next(a for a in mf["dados"] if a["ticker"] == t)
        liq_rows.append([
            label(t, mf), money(r["volume_financeiro_medio_63d"], r["moeda"]),
            share(audit["pct_open_igual_fechamento_anterior"]), audit["primeira_barra"], str(audit["barras"]),
        ])

    signal_rows = []
    for t in lines:
        last = d["last"][t]
        signal_rows.append([
            label(t, mf), str(last.name.date()),
            "comprado" if int(last["position"]) == 1 else "fora (caixa)",
            pct(float(last["drawdown"]) * 100),
        ])

    corr = d["corr"]
    corr_cc = corr.loc["CCJ", "URA"]
    corr_spy = corr.loc[["SRUUF", "LEU", "PALAF", "CCJ"], "SPY"]

    notes = "".join(
        f"<li><strong>{label(t, mf)}</strong>: {html.escape(meta['nota'])}</li>"
        for t, meta in mf["ativos"].items() if meta["nota"]
    )
    roles = "".join(
        f"<tr><td>{label(t, mf)}</td><td>{html.escape(meta['nome'])}</td><td>{html.escape(meta['papel'])}</td><td>{meta['moeda']}</td></tr>"
        for t, meta in mf["ativos"].items()
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cadeia do Urânio: SPUT, Centrus, Paladin e Cameco</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1d232b; --muted:#5b6570; --line:#dcd8cf; --accent:#1f5f8b; --warn:#9a5b00; --card:#ffffff; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#14181d; --fg:#e6e9ed; --muted:#9aa4ae; --line:#2c333b; --accent:#7fb6dd; --warn:#e0a44a; --card:#1b2026; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:32px 16px 64px; }}
h1 {{ font-size:1.9rem; line-height:1.25; margin:0 0 6px; }}
h2 {{ font-size:1.3rem; margin:40px 0 12px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
.meta {{ color:var(--muted); font-size:.9rem; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:16px 20px; margin:16px 0; }}
.warn {{ border-left:4px solid var(--warn); }}
.key {{ border-left:4px solid var(--accent); }}
.scroll {{ overflow-x:auto; }}
table {{ border-collapse:collapse; width:100%; font-size:.88rem; font-variant-numeric:tabular-nums; }}
th, td {{ padding:6px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }}
th:first-child, td:first-child, table.text th, table.text td {{ text-align:left; }}
th {{ color:var(--muted); font-weight:600; }}
figure {{ margin:16px 0; }}
figure img {{ width:100%; height:auto; background:#fff; border:1px solid var(--line); border-radius:6px; }}
figcaption {{ color:var(--muted); font-size:.85rem; margin-top:4px; }}
small {{ color:var(--muted); }}
li {{ margin:4px 0; }}
</style>
</head>
<body>
<main>
<h1>Cadeia do Urânio: exposição física (SPUT), enriquecimento (Centrus) e mineração (Paladin, Cameco)</h1>
<p class="meta">Pregões até {last_bar} · Gerado em {html.escape(mf["gerado_em_utc"])} (UTC) · Estratégia Momentum ATR do repositório (20/14/2,5; sinal em close[t], execução em open[t+1]; 0,15% por ponta) · Modo pesquisa, <em>shadow mode</em>, nenhum ativo aprovado para capital</p>

<h2>1. Conclusão executiva</h2>
<div class="card key">
<ul>
<li><strong>Buy &amp; Hold superou o Momentum ATR em Sharpe em {bh_wins} de {len(lines)} linhas de negociação.</strong> O filtro de tendência cortou o drawdown máximo em algumas linhas (Cameco {pct(m.loc["CCJ","mom_max_dd_pct"])} contra {pct(m.loc["CCJ","bh_max_dd_pct"])}; U.UN {pct(m.loc["U-UN.TO","mom_max_dd_pct"])} contra {pct(m.loc["U-UN.TO","bh_max_dd_pct"])}), mas ficou fora de alta relevante: a exposição média foi de apenas 36% a 43% do tempo.</li>
<li><strong>O resultado depende do regime.</strong> Em 2020–2022 a estratégia funcionou em Paladin e Centrus. De 2023 em diante perdeu dinheiro em Paladin (ASX) e na SPUT, e só a Cameco melhorou (Sharpe {num(per.query("ticker=='CCJ' and periodo=='2023-hoje'")["mom_sharpe"].iloc[0])}).</li>
<li><strong>Nenhum ativo passa no filtro estatístico do projeto.</strong> A maior probabilidade DSR foi {num(dsr_max, 2)}, abaixo de 0,95, e esse DSR só desconta a escolha entre 4 ativos, não os parâmetros escolhidos em pesquisas anteriores.</li>
<li><strong>Os custos pesam.</strong> Com 64 a 85 operações no período, a 0,35% por ponta a U.UN já fica negativa. A 0,50%, o retorno da Cameco cai de {pct(st.query("ticker=='CCJ' and scenario=='base_15bps'")["total_return"].iloc[0]*100, 0)} para {pct(st.query("ticker=='CCJ' and scenario=='severo_50bps'")["total_return"].iloc[0]*100, 0)}.</li>
<li><strong>O risco é de setor.</strong> A volatilidade anual vai de {share(d["beta"].loc["SRUUF","vol_anual_pct"],0)} (SPUT) a {share(d["beta"].loc["LEU","vol_anual_pct"],0)} (Centrus). A Cameco tem correlação de {num(corr_cc)} com o ETF URA, e na prática funciona como o próprio setor. A correlação com o S&amp;P 500 fica entre {num(corr_spy.min())} e {num(corr_spy.max())}.</li>
<li><strong>Sinal atual:</strong> {signal_text}</li>
</ul>
</div>

<h2>2. O que cada ativo representa na cadeia</h2>
<p>Só dois dos ativos são mineradores de fato. A SPUT não produz nada: ela compra e guarda U3O8, e por isso funciona como termômetro do preço à vista. A Centrus está na etapa seguinte da cadeia, o enriquecimento. Tratar os quatro como "produtores" misturaria riscos diferentes.</p>
<div class="scroll"><table class="text"><thead><tr><th>Listagem</th><th>Empresa</th><th>Papel na cadeia</th><th>Moeda</th></tr></thead><tbody>{roles}</tbody></table></div>
<ul>
<li><strong>SPUT (U.UN/SRUUF)</strong>: exposição quase pura ao preço spot, sem risco operacional de mina. Os riscos próprios são o prêmio ou desconto sobre o valor patrimonial (NAV) e as emissões de novas cotas, que financiam compras de urânio. O NAV não foi coletado neste estudo.</li>
<li><strong>Centrus (LEU)</strong>: enriquecimento e combustível (LEU e HALEU). O valor depende mais de contratos e política energética dos EUA do que do preço spot, e é o ativo mais volátil do grupo.</li>
<li><strong>Paladin (PDN/PALAF)</strong>: produtora que retomou a mina Langer Heinrich. O risco central é a execução do <em>ramp-up</em> (volume e custo por libra).</li>
<li><strong>Cameco (CCJ)</strong>: maior produtora integrada listada nas Américas (mineração, conversão e participação na Westinghouse). Tem o perfil mais diversificado e a maior liquidez.</li>
</ul>

<h2>3. Fundamentos (último exercício, na moeda contábil)</h2>
<div class="card warn"><strong>Fonte e limites:</strong> dados do Yahoo Finance via yfinance, coletados em {html.escape(d["fund"]["coletado_em_utc"])}, <strong>sem conferência com as demonstrações oficiais</strong>. Margens e crescimento foram calculados aqui a partir da DRE anual, todos na moeda contábil de cada empresa. Os múltiplos prontos do provedor (P/L, EV/Receita) foram descartados: para Cameco e Paladin eles misturam a moeda de cotação com a moeda contábil, e para a SPUT o lucro é marcação a mercado do estoque de urânio.</div>
{table(["Ativo", "Exercício", "Receita", "Cresc. a/a", "Margem bruta", "Margem operacional", "Lucro líquido", "Valor de mercado"], fundamentals_rows(d["fund"], mf))}
<p><small>Exercício fiscal da Paladin termina em 30/jun. Valor de mercado na moeda de cotação da listagem principal.</small></p>

<h2>4. Evidência quantitativa: Momentum ATR vs Buy &amp; Hold</h2>
<p>Mesmo motor causal do repositório (<code>src/backtest/engine.py</code>), capital inicial de 100 mil na moeda da listagem. O Buy &amp; Hold compra no primeiro <em>open</em> e vende no último fechamento, pagando os mesmos 0,15% por ponta. As métricas do Buy &amp; Hold usam a mesma função de cálculo do motor.</p>
{table(["Listagem", "Moeda", "Pregões", "Operações", "Mom. retorno", "Mom. Sharpe", "Mom. DD máx.", "B&H retorno", "B&H Sharpe", "B&H DD máx.", "Exposição"], perf_rows)}
{img("u3_momentum_vs_bh.png", "Patrimônio do Momentum ATR vs Buy & Hold nas quatro listagens principais (escala log)")}
{img("u1_preco_normalizado.png", "Preço normalizado das linhas em USD desde a estreia da SRUUF (escala log)")}

<h2>5. Estabilidade por regime (2020–2022 vs 2023 em diante)</h2>
<div class="card warn">Os parâmetros (20/14/2,5) são o padrão do repositório e não foram otimizados nestes ativos. Mesmo assim, o período de 2023 em diante é <strong>pseudo fora da amostra</strong>: o padrão foi escolhido em pesquisas que já usaram esses anos. A classificação é <code>retrospective_pseudo_oos</code>, como na auditoria OOS do projeto.</div>
{table(["Listagem", "Período", "1º pregão", "Mom. retorno", "Mom. Sharpe", "B&H retorno", "B&H Sharpe"], period_rows)}

<h2>6. Deflated Sharpe Ratio</h2>
<p>Bailey &amp; López de Prado, com a implementação de <code>src/backtest/statistics.py</code>. Número de testes = 4 ativos principais. O Sharpe de referência é o máximo esperado ao acaso entre 4 tentativas com a dispersão observada ({num(mf["dsr"]["desvio_dos_sharpes"], 3)}).</p>
{table(["Listagem", "Sharpe observado", "Sharpe de referência", "Probabilidade DSR"], dsr_rows)}
<p><small>O critério usual de aprovação é DSR ≥ 0,95. O PBO não foi calculado porque o repositório ainda não o implementa (registrado como <code>null</code> no manifesto).</small></p>

<h2>7. Estresse de custos</h2>
<p>Matriz padrão de <code>src/backtest/stress.py</code>: base (0,15% por ponta), liquidez reduzida (0,35% + 0,15% de slippage no stop) e severo (0,50% + 0,30%).</p>
{table(["Listagem", "Base 15 bps", "Liquidez reduzida", "Severo 50 bps"], stress_rows)}

<h2>8. Risco, correlação e beta</h2>
<p>Retornos diários das linhas em USD a partir de 22/07/2021, a primeira data comum a todas.</p>
{img("u4_correlacao.png", "Correlação dos retornos diários entre as linhas em USD")}
{table(["Linha", "Beta vs URA", "Beta vs SPY", "Vol. anual"], beta_rows)}
{img("u2_drawdown.png", "Drawdown desde o topo anterior")}

<h2>9. Liquidez e qualidade das listagens</h2>
{table(["Listagem", "Vol. financeiro médio (63 pregões)", "Aberturas = fech. anterior", "1º pregão válido", "Pregões"], liq_rows)}
<p>A coluna "Aberturas = fech. anterior" mostra a fração de pregões em que a abertura repete o fechamento anterior, sinal de que não houve negócio na abertura. Na PALAF isso passa de 20%. O backtest executa na abertura, então o resultado da PALAF não é confiável e a referência para a Paladin é a PDN na ASX. Para SPUT, as linhas TSX (U.UN) e OTCQX (SRUUF) são o mesmo ativo em moedas diferentes.</p>

<h2>10. Sinal atual (shadow mode)</h2>
{table(["Listagem", "Último pregão", "Estado Momentum ATR", "Drawdown da estratégia"], signal_rows)}
<p><small>Informativo. Nenhuma ordem é gerada: o OMS do projeto é exclusivamente paper e estes ativos não estão em <code>config/oms_simulation.json</code>.</small></p>

<h2>11. O que mudaria esta leitura</h2>
<ul>
<li><strong>A favor do Momentum ATR:</strong> DSR acima de 0,95 em dados novos (depois desta data), com os parâmetros congelados, e Sharpe estável entre regimes.</li>
<li><strong>Contra a tese setorial:</strong> preço spot e de longo prazo do U3O8 em queda persistente. A SPUT é o termômetro mais direto: acompanhe o desconto sobre o NAV e as emissões.</li>
<li><strong>Paladin:</strong> produção e custo por libra fora do guidance nos relatórios trimestrais da ASX.</li>
<li><strong>Centrus:</strong> mudanças nos contratos de HALEU/LEU e nas restrições de importação de urânio enriquecido russo para os EUA.</li>
<li><strong>Cameco:</strong> desempenho de McArthur River/Key Lake e da Westinghouse. Com correlação de {num(corr_cc)} com o URA, o principal risco da Cameco é o do setor.</li>
</ul>

<h2>12. Qualidade de dados, fontes e pendências</h2>
<div class="card warn"><ul>{notes}</ul></div>
<ul>
<li>Preços diários: Yahoo Finance via yfinance, <code>auto_adjust=False</code>, validados com <code>validate_ohlc</code>. Hashes SHA-256 de cada Parquet estão em <code>results/uranium_research/manifesto_uranio.json</code>.</li>
<li>Nenhuma série foi preenchida ou sintetizada. Linhas inválidas foram descartadas e contadas no manifesto.</li>
<li><strong>Pendente de conferência humana:</strong> fundamentos contra as demonstrações oficiais (Centrus: 10-K/10-Q na SEC; Cameco: relatório anual/MD&amp;A e 40-F; Paladin: relatório anual e trimestrais na ASX; SPUT: NAV e libras de U3O8 publicados pela Sprott). Preço spot do U3O8 e prêmio/desconto da SPUT não foram coletados.</li>
</ul>
<p><small>Reproduzir: <code>python scripts/analisar_uranio.py</code> e depois <code>python scripts/build_relatorio_uranio.py</code>. Commit de referência: <code>{html.escape(mf["git"]["commit_sha"][:12])}</code> (árvore com alterações: {mf["git"]["dirty"]}).</small></p>

<div class="card"><small><strong>Aviso:</strong> material de pesquisa produzido com os modelos do repositório iitauquant para fins educacionais. Não é recomendação de investimento nem oferta de valores mobiliários. Resultados passados, especialmente em amostra, não garantem resultados futuros. Nenhuma ordem real foi enviada.</small></div>
</main>
</body>
</html>
"""


def main() -> None:
    manifest = json.loads((RESEARCH / "manifesto_uranio.json").read_text(encoding="utf-8"))
    us_last_bar = next(a["ultima_barra"] for a in manifest["dados"] if a["ticker"] == "SPY")
    output = ROOT / "relatorios" / f"cadeia_uranio_analise_{us_last_bar}.html"
    output.write_text(build(), encoding="utf-8")
    print(f"Relatório gerado: {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
