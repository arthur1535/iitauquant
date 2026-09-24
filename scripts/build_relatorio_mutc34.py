"""Gera o relatório HTML revisado de Micron/MUTC34 a partir de snapshots locais.

O script é deliberadamente offline: não baixa cotações nem transforma hipóteses
de cenário em recomendações automáticas. Os gráficos são gerados por
scripts/gerar_graficos_micron.py usando os arquivos locais em data/market.
"""

from __future__ import annotations

import base64
import csv
import html
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "micron_research"
REPORTS = ROOT / "relatorios"
GRAPHICS = REPORTS / "graficos"
GRAPHICS.mkdir(parents=True, exist_ok=True)


def read_json(name: str) -> dict:
    with (RESULTS / name).open(encoding="utf-8") as fh:
        return json.load(fh)


def image_data(name: str) -> str:
    source = RESULTS / name
    destination = GRAPHICS / name
    shutil.copy2(source, destination)
    return base64.b64encode(source.read_bytes()).decode("ascii")


def number(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def percent(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}%".replace(".", ",")


def esc(value: object) -> str:
    return html.escape(str(value))


data = read_json("micron_summary.json")
with (RESULTS / "micron_comparative_metrics.csv").open(encoding="utf-8", newline="") as fh:
    metrics = list(csv.DictReader(fh))

mu_close = float(data["mu_close"])
mutc_close = float(data["mutc_close"])
fx = float(data["usd_brl"])
ratio = float(data["bdr_ratio"])
theoretical = float(data["theoretical_bdr"])
spread = float(data["parity_spread_pct"])
market_cap_b = mu_close * 1129.393151 / 1000
equity_b = 100.724
debt_b = 0.582 + 5.140
cash_b = 24.995
net_cash_b = cash_b - debt_b
price_book = market_cap_b / equity_b


metric_rows = []
for row in metrics:
    metric_rows.append(
        "<tr>"
        f"<td><strong>{esc(row['ticker'])}</strong></td>"
        f"<td>{esc(row['bars'])}</td><td>{esc(row['trades'])}</td>"
        f"<td>{esc(row['exposure_pct'])}%</td><td>{esc(row['mom_ret_pct'])}%</td>"
        f"<td>{esc(row['mom_cagr_pct'])}%</td><td>{esc(row['mom_vol_pct'])}%</td>"
        f"<td>{esc(row['mom_sharpe'])}</td><td>{esc(row['mom_max_dd_pct'])}%</td>"
        f"<td>{esc(row['bh_ret_pct'])}%</td><td>{esc(row['bh_max_dd_pct'])}%</td>"
        "</tr>"
    )


scenario_specs = [
    ("Baixista", 750.0, 4.90, "Memória entra em excesso, capex de IA desacelera ou exportações restringem a demanda."),
    ("Base", 1250.0, 5.20, "Execução operacional favorável, mas com a ciclicidade de DRAM/HBM ainda presente."),
    ("Otimista", 1500.0, 5.40, "HBM e DRAM permanecem apertadas e a expansão de capacidade converte-se em margem."),
]
scenario_rows = []
for label, mu, scenario_fx, trigger in scenario_specs:
    bdr = mu * scenario_fx / ratio
    return_pct = (bdr / mutc_close - 1) * 100
    cls = {"Baixista": "bear", "Base": "base", "Otimista": "bull"}[label]
    scenario_rows.append(
        f"<tr><td class='scenario-{cls}'><strong>{label}</strong></td>"
        f"<td>US$ {number(mu)}</td><td>R$ {number(scenario_fx, 2)}</td>"
        f"<td>R$ {number(bdr)}</td><td>{percent(return_pct)}</td>"
        f"<td>{esc(trigger)} Hipótese ilustrativa; sem probabilidade calibrada.</td></tr>"
    )


css = """
:root{--ink:#0f172a;--muted:#475569;--paper:#f8fafc;--card:#fff;--line:#e2e8f0;
--blue:#0369a1;--cyan:#38bdf8;--green:#047857;--red:#b91c1c;--amber:#b45309;
--shadow:0 10px 25px -5px rgba(15,23,42,.07),0 8px 10px -6px rgba(15,23,42,.04)}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);
font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;line-height:1.6}
a{color:var(--blue);text-underline-offset:2px}.wrap{max-width:1200px;margin:auto;padding:32px 24px}
header{background:linear-gradient(135deg,#071527,#0f172a 52%,#034b75);color:#fff;
border-top:6px solid var(--cyan);padding:42px;border-radius:8px;box-shadow:var(--shadow)}
.eyebrow{color:var(--cyan);font-weight:750;letter-spacing:.09em;text-transform:uppercase;font-size:.78rem}
h1{font-size:clamp(2rem,3.8vw,3.4rem);line-height:1.1;margin:.45rem 0 1rem;max-width:1000px}
h2{font-size:1.55rem;line-height:1.25;margin:0 0 18px}h3{font-size:1.08rem;margin:0 0 8px}
.meta{color:#cbd5e1;font-size:.88rem}.verdict{margin-top:22px;padding:20px 24px;
border-left:5px solid var(--cyan);background:rgba(255,255,255,.08);border-radius:0 8px 8px 0}
.grid{display:grid;gap:20px}.kpis{grid-template-columns:repeat(4,1fr);margin:24px 0}
.kpi,.card,section{background:var(--card);border:1px solid var(--line);border-radius:8px;box-shadow:var(--shadow)}
.kpi{padding:20px}.kpi b{display:block;font-size:1.6rem}.kpi span{color:var(--muted);font-size:.82rem}
section{padding:30px;margin:24px 0}.two{grid-template-columns:1fr 1fr}.three{grid-template-columns:repeat(3,1fr)}
.card{padding:20px;box-shadow:none}.positive{border-top:4px solid var(--green)}
.negative{border-top:4px solid var(--red)}.neutral{border-top:4px solid var(--blue)}
.amber{border-top:4px solid var(--amber)}.tag{display:inline-block;padding:3px 9px;border-radius:4px;
background:#e0f2fe;color:#075985;font-size:.73rem;font-weight:750;text-transform:uppercase;letter-spacing:.04em}
.callout{padding:18px 20px;background:#f0f9ff;border-left:5px solid var(--blue);border-radius:0 6px 6px 0;margin:18px 0}
.warn{background:#fffbeb;border-left-color:var(--amber)}.small{font-size:.84rem;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:.9rem;margin-top:12px}th,td{padding:10px 12px;
border-bottom:1px solid var(--line);text-align:right;vertical-align:top}th:first-child,td:first-child{text-align:left}
thead th{background:#f8fafc;color:#334155;font-weight:700}tbody tr:last-child td{border-bottom:0}
.scenario-bear{color:var(--red)}.scenario-base{color:var(--blue)}.scenario-bull{color:var(--green)}
.img-box{text-align:center;margin:22px 0}.img-box img{max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px}
.footer{color:var(--muted);font-size:.82rem;padding:14px 4px 40px;border-top:1px solid var(--line);margin-top:30px}
@media(max-width:860px){.wrap{padding:16px}header,section{padding:22px}.kpis,.two,.three{grid-template-columns:1fr}
table{font-size:.8rem}th,td{padding:8px 6px}}
"""

trade_img = image_data("mutc34_trade_setup.png")
equity_img = image_data("micron_equity_drawdown.png")
peers_img = image_data("micron_peers_comparison.png")

html_content = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Micron Technology / MUTC34 — revisão quantitativa e fundamentalista</title><style>{css}</style></head>
<body><main class="wrap">
<header>
  <div class="eyebrow">Pesquisa quantitativa e fundamentalista • NASDAQ: MU • B3: MUTC34</div>
  <h1>Micron Technology: crescimento de memória, preço exigente e risco de ciclo</h1>
  <p class="meta">Snapshot local de 24 de setembro de 2026 • Revisão editorial: 24 de setembro de 2026 • Horizonte: 12–24 meses • MUTC34 usa a proporção 6:1 informada no programa CVM consultado</p>
  <div class="verdict"><strong>Postura de pesquisa: watchlist / compra somente após validação de preço, liquidez e risco.</strong><br>
  A Micron tem exposição relevante a DRAM, HBM e SSDs para IA, mas memória é um mercado cíclico e intensivo em capital. O snapshot quantitativo mostra exposição média de {esc(metrics[1]['exposure_pct'])}% no sinal MUTC34, e não investimento permanente de 33% do patrimônio. Nenhum cenário abaixo é promessa, ordem ou recomendação personalizada.</div>
</header>

<div class="grid kpis">
  <div class="kpi"><b>R$ {number(mutc_close)}</b><span>MUTC34 — fechamento do snapshot local</span></div>
  <div class="kpi"><b>US$ {number(mu_close)}</b><span>MU — fechamento usado na paridade</span></div>
  <div class="kpi"><b>R$ {number(theoretical)}</b><span>Paridade teórica (MU × câmbio ÷ 6); spread {percent(spread,2)}</span></div>
  <div class="kpi"><b>{number(price_book,1)}x</b><span>P/VP indicativo: market cap local / patrimônio do snapshot</span></div>
</div>

<section><h2>1. O que a evidência sustenta</h2><div class="grid three">
  <div class="card positive"><span class="tag">Produto</span><h3>HBM e memória de IA</h3><p>HBM, DRAM e SSDs para data centers são vetores de crescimento. A companhia disputa esse mercado com SK Hynix e Samsung; a tese depende de rendimento, preço e capacidade.</p></div>
  <div class="card neutral"><span class="tag">Contratos</span><h3>Visibilidade parcial</h3><p>O material de resultados usado no snapshot menciona 16 acordos de clientes para HBM. Isso melhora a visibilidade, mas não equivale a 100% da produção vendida, a preço fixo ou a lucro garantido.</p></div>
  <div class="card amber"><span class="tag">Ciclo</span><h3>Capital e oferta</h3><p>Novas fábricas, depreciação, capex e competição podem comprimir margens quando a oferta de memória cresce mais rápido que a demanda.</p></div>
</div><div class="callout warn"><strong>Limite da fonte:</strong> números trimestrais de 10-Q são reportados, não auditados. A edição separa fatos da companhia, estimativas secundárias e hipóteses do analista.</div></section>

<section><h2>2. Snapshot de preço, balanço e BDR</h2><div style="overflow-x:auto"><table>
<thead><tr><th>Item</th><th>Valor</th><th>Leitura</th></tr></thead><tbody>
<tr><td>MU / MUTC34</td><td>US$ {number(mu_close)} / R$ {number(mutc_close)}</td><td>Fechamentos do arquivo local; não são cotação em tempo real.</td></tr>
<tr><td>USD/BRL</td><td>R$ {number(fx,4)}</td><td>Usado apenas na conversão teórica.</td></tr>
<tr><td>Patrimônio líquido</td><td>US$ {number(equity_b)} bi</td><td>Valor do snapshot contábil; confirme no 10-Q mais recente.</td></tr>
<tr><td>Caixa e equivalentes</td><td>US$ {number(cash_b)} bi</td><td>Inclui caixa e investimentos de curto prazo da base local.</td></tr>
<tr><td>Dívida apresentada no snapshot</td><td>US$ {number(debt_b)} bi</td><td>US$ 0,582 bi + US$ 5,140 bi; não confundir com passivos totais.</td></tr>
<tr><td>Caixa líquido indicativo</td><td>US$ {number(net_cash_b)} bi</td><td>Caixa menos a dívida selecionada; não é imunidade a volatilidade.</td></tr>
<tr><td>Capitalização estimada</td><td>US$ {number(market_cap_b)} bi</td><td>MU × 1.129,4 milhões de ações; aproximação local.</td></tr>
</tbody></table></div>
<p class="small">P/VP indicativo de {number(price_book,1)}x é cálculo de aproximação, não valuation completo. O lucro futuro depende do ciclo e não foi convertido em preço-alvo.</p></section>

<section><h2>3. Evidência quantitativa local: Momentum ATR</h2>
<p>A tabela resume o arquivo <code>micron_comparative_metrics.csv</code>. O motor usa entrada no pregão seguinte, custo de 0,15% por lado, caixa sem remuneração e gap de stop na abertura. A exposição é média do período; Sharpe do sistema e do Buy &amp; Hold não deve ser comparado sem a mesma convenção de taxa livre de risco e anualização.</p>
<div style="overflow-x:auto"><table><thead><tr><th>Ativo</th><th>Barras</th><th>Trades</th><th>Exposição média</th><th>Retorno Mom.</th><th>CAGR Mom.</th><th>Vol. Mom.</th><th>Sharpe Mom.</th><th>DD Mom.</th><th>Retorno B&amp;H</th><th>DD B&amp;H</th></tr></thead><tbody>{''.join(metric_rows)}</tbody></table></div>
<div class="callout"><strong>Leitura:</strong> o backtest é uma amostra histórica local, não validação fora da amostra. O resultado de MUTC34 (+{esc(metrics[1]['mom_ret_pct'])}% no Mom. e +{esc(metrics[1]['bh_ret_pct'])}% no B&amp;H) convive com drawdowns de {esc(metrics[1]['mom_max_dd_pct'])}% e {esc(metrics[1]['bh_max_dd_pct'])}%, respectivamente.</div>
</section>

<section><h2>4. Gráficos do snapshot local</h2>
<div class="img-box"><img src="data:image/png;base64,{trade_img}" alt="MUTC34, preço histórico e distâncias ATR ilustrativas"><p class="small">Preço histórico local; níveis de preço menos ATR são referências ilustrativas, não ordens automáticas.</p></div>
<div class="img-box"><img src="data:image/png;base64,{equity_img}" alt="Curvas históricas simuladas de MU e MUTC34"><p class="small">Curvas simuladas com custos declarados; não representam resultado futuro nem incluem impostos.</p></div>
<div class="img-box"><img src="data:image/png;base64,{peers_img}" alt="Comparação histórica de Micron e pares"><p class="small">Preços locais normalizados; sem reinvestimento de dividendos, custos ou previsão.</p></div>
</section>

<section><h2>5. Cenários ilustrativos para 12–24 meses</h2><div style="overflow-x:auto"><table><thead><tr><th>Cenário</th><th>MU</th><th>USD/BRL</th><th>MUTC34 teórico</th><th>Variação vs snapshot</th><th>Hipótese</th></tr></thead><tbody>{''.join(scenario_rows)}</tbody></table></div>
<p class="small">Fórmula: (MU × USD/BRL) ÷ 6. Os valores são sensibilidades e não previsões; não há probabilidades calibradas, custo de execução, imposto ou spread futuro incluído.</p></section>

<section><h2>6. Riscos e disciplina de execução</h2><div class="grid two">
  <div class="card negative"><h3>Riscos que invalidam a tese</h3><ul><li>queda de preço de DRAM/HBM ou excesso de oferta;</li><li>atrasos e capex acima do retorno nas novas fábricas;</li><li>perda de clientes, rendimento inferior ou competição asiática;</li><li>export controls, tarifas, concentração em data centers e câmbio;</li><li>gap de abertura que ultrapasse qualquer preço de proteção.</li></ul></div>
  <div class="card neutral"><h3>Como ler ATR</h3><p>O preço menos 2,5×ATR14 do snapshot é R$ {number(float(data['stop_25_atr']))}; isso é uma distância de risco ilustrativa, não um stop garantido. Um stop pode sofrer slippage, ser executado na abertura e não preservar capital. A posição deve ser dimensionada antes da ordem e revisada conforme a liquidez real.</p><p>As médias móveis e máximas de 52 semanas são referências históricas, não alvos.</p></div>
</div></section>

<section><h2>7. Fontes, governança e conclusão</h2><ul class="small">
<li><a href="https://investors.micron.com/news-releases">Micron Investor Relations</a>: releases, apresentações e chamadas de resultados; fatos da companhia devem ser confirmados no arquivamento aplicável.</li>
<li><a href="https://www.sec.gov/edgar/browse/?CIK=723125">SEC EDGAR — Micron Technology</a>: 10-K/10-Q/8-K. O 10-Q é trimestral e não auditado; o 10-K anual é a referência auditada.</li>
<li><a href="https://sistemas.cvm.gov.br/asp/cvmwww/registro/ofertasreg2/Bdrdet.asp?Nr_Ano=2019&amp;Nr_Proc=1868&amp;Sg_uf=RJ&amp;status=R">CVM — programa MUTC34</a>: proporção consultada de 6 BDRs para 1 ação ordinária; confira o programa vigente antes de operar.</li>
<li><strong>Laboratório iitauquant:</strong> micron_summary.json, micron_comparative_metrics.csv, dados locais em data/market e motor de backtest. Nenhum dado foi baixado por este gerador.</li>
</ul><div class="callout"><strong>Conclusão:</strong> MUTC34 é uma candidata de alta qualidade operacional, porém cíclica e volátil. A recomendação prudente é manter em watchlist, validar o próximo 10-Q e o preço/paridade em tempo real e só então definir tamanho e ponto de entrada. Este documento é pesquisa educacional; não é recomendação individual.</div></section>

<div class="footer">Relatório gerado offline em 24 de setembro de 2026 • snapshot local e histórico • revisão humana necessária antes de qualquer decisão • nenhuma ordem foi executada.</div>
</main></body></html>
"""

report = REPORTS / "micron_mutc34_analise_2026-09-24.html"
report.write_text(html_content, encoding="utf-8")
print(f"Relatório gerado: {report}")
