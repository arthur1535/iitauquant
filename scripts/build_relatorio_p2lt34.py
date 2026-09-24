"""Renderiza offline o relatório histórico de Palantir, sem atualizar pesquisa ou preços."""
from __future__ import annotations

import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results" / "palantir_research"
RELATORIOS_DIR = ROOT / "relatorios"

# Os arquivos de pesquisa e as imagens originais são apenas lidos.
b64_trade_setup = base64.b64encode((RESULTS_DIR / "p2lt34_trade_setup.png").read_bytes()).decode("ascii")
b64_equity_drawdown = base64.b64encode((RESULTS_DIR / "palantir_equity_drawdown.png").read_bytes()).decode("ascii")
user_data = json.loads((RESULTS_DIR / "user_position_summary.json").read_text(encoding="utf-8"))
entry = user_data["user_entry_price"]
bdr = user_data["p2lt_close"]
us_price = user_data["pltr_close"]
fx = user_data["usd_brl"]
ratio = user_data["bdr_ratio"]
atr = user_data["atr14_bdr"]
if min(entry, bdr, us_price, fx, ratio, atr) <= 0 or ratio != 3:
    raise ValueError("Snapshot inválido ou proporção divergente do programa BDR documentado.")
parity = us_price * fx / ratio
spread = (bdr / parity - 1) * 100
paper_return = (bdr / entry - 1) * 100
stop20, stop25 = bdr - 2 * atr, bdr - 2.5 * atr

def br(value: float, digits: int = 2) -> str:
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")

# Valores em milhares de US$, conforme 10-Q 2T26; FCF simples = CFO - capex.
revenue, prior_revenue = 1_935_464, 1_003_697
gross_margin = 1_638_594 / revenue * 100
prior_gross_margin = 810_763 / prior_revenue * 100
operating_margin = 912_004 / revenue * 100
prior_operating_margin = 269_317 / prior_revenue * 100
net_margin = 1_061_890 / revenue * 100
fcf_h1 = (2_115_332 - 21_955) / 1_000_000

html_content = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Palantir / P2LT34 — fundamentos e revisão de evidência histórica</title>
  <style>
    :root {{
      --ink: #0f172a;
      --muted: #475569;
      --paper: #f8fafc;
      --card: #ffffff;
      --line: #e2e8f0;
      --palantir: #0284c7;
      --palantir-dark: #0f172a;
      --palantir-glow: #38bdf8;
      --green: #059669;
      --green-bg: #ecfdf5;
      --red: #dc2626;
      --red-bg: #fef2f2;
      --amber: #d97706;
      --amber-bg: #fffbeb;
      --gold: #f59e0b;
      --shadow: 0 10px 25px -5px rgba(15,23,42,0.07), 0 8px 10px -6px rgba(15,23,42,0.04);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
    }}
    a {{ color: var(--palantir); text-decoration-thickness: 1px; text-underline-offset: 2px; }}
    .wrap {{ max-width: 1200px; margin: auto; padding: 32px 24px; }}
    header {{
      background: linear-gradient(135deg, #090d16 0%, #0f172a 50%, #034b75 100%);
      color: #fff;
      border-top: 6px solid var(--palantir-glow);
      padding: 44px;
      border-radius: 8px;
      box-shadow: var(--shadow);
      position: relative;
      overflow: hidden;
    }}
    header::after {{
      content: "";
      position: absolute;
      top: -40px;
      right: -40px;
      width: 260px;
      height: 260px;
      background: radial-gradient(circle, rgba(56,189,248,0.18) 0%, transparent 70%);
      border-radius: 50%;
      pointer-events: none;
    }}
    .eyebrow {{
      color: var(--palantir-glow);
      font-weight: 750;
      letter-spacing: .09em;
      text-transform: uppercase;
      font-size: .8rem;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .eyebrow::before {{
      content: "";
      width: 8px;
      height: 8px;
      background: var(--palantir-glow);
      border-radius: 50%;
      display: inline-block;
    }}
    .meta {{ color: #94a3b8; font-size: .88rem; margin-top: 6px; }}
    h1 {{
      font-size: clamp(2rem, 3.8vw, 3.4rem);
      line-height: 1.1;
      margin: .4rem 0 1rem;
      max-width: 980px;
      font-weight: 800;
      letter-spacing: -0.025em;
    }}
    h2 {{
      font-size: 1.55rem;
      line-height: 1.25;
      margin: 0 0 18px;
      color: #0f172a;
      font-weight: 750;
      letter-spacing: -0.02em;
    }}
    h3 {{ font-size: 1.1rem; margin: 0 0 8px; font-weight: 700; }}
    .verdict {{
      margin: 24px 0 0;
      padding: 22px 26px;
      border-left: 5px solid var(--palantir-glow);
      background: rgba(255,255,255,0.08);
      backdrop-filter: blur(8px);
      border-radius: 0 8px 8px 0;
      font-size: 1.05rem;
      line-height: 1.6;
    }}
    .grid {{ display: grid; gap: 20px; }}
    .kpis {{ grid-template-columns: repeat(4, 1fr); margin: 24px 0; }}
    .kpi, .card, section {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }}
    .kpi {{ padding: 20px 22px; transition: transform .15s ease; }}
    .kpi:hover {{ transform: translateY(-2px); }}
    .kpi b {{
      display: block;
      font-size: 1.7rem;
      line-height: 1.1;
      color: #0f172a;
      font-weight: 800;
      letter-spacing: -0.02em;
    }}
    .kpi span {{
      color: var(--muted);
      font-size: .82rem;
      font-weight: 500;
      margin-top: 4px;
      display: block;
    }}
    .kpi.highlight {{
      border-top: 4px solid var(--green);
      background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%);
    }}
    .kpi.highlight b {{ color: var(--green); }}
    section {{ padding: 32px; margin: 24px 0; }}
    .two {{ grid-template-columns: 1fr 1fr; }}
    .three {{ grid-template-columns: repeat(3, 1fr); }}
    .four {{ grid-template-columns: repeat(4, 1fr); }}
    .card {{ padding: 22px; box-shadow: none; border: 1px solid var(--line); border-radius: 6px; background: #ffffff; }}
    .card p:last-child {{ margin-bottom: 0; }}
    .tag {{
      display: inline-block;
      padding: 4px 10px;
      border-radius: 4px;
      background: #f1f5f9;
      color: #334155;
      font-size: .74rem;
      font-weight: 750;
      text-transform: uppercase;
      letter-spacing: .05em;
      margin-bottom: 10px;
    }}
    .positive {{ border-top: 4px solid var(--green); }}
    .negative {{ border-top: 4px solid var(--red); }}
    .neutral {{ border-top: 4px solid var(--palantir); }}
    .amber {{ border-top: 4px solid var(--amber); }}
    .user-card {{
      border: 2px solid var(--green);
      background: #f0fdf4;
      padding: 24px;
      border-radius: 8px;
      margin: 20px 0;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: .92rem; margin-top: 14px; }}
    th, td {{ padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: right; vertical-align: top; }}
    th:first-child, td:first-child {{ text-align: left; }}
    thead th {{ background: #f8fafc; color: #334155; font-weight: 700; border-bottom: 2px solid var(--line); }}
    tbody tr:hover {{ background: #f8fafc; }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    .callout {{
      padding: 20px 22px;
      background: #f0f9ff;
      border-left: 5px solid var(--palantir);
      border-radius: 0 6px 6px 0;
      margin: 18px 0;
      color: #0369a1;
      font-size: .96rem;
      line-height: 1.55;
    }}
    .callout-success {{
      background: #ecfdf5;
      border-left: 5px solid var(--green);
      color: #065f46;
    }}
    .callout strong {{ color: inherit; font-weight: 750; }}
    .small {{ font-size: .84rem; color: var(--muted); }}
    .barrow {{ display: grid; grid-template-columns: 160px 1fr 100px; gap: 14px; align-items: center; margin: 12px 0; }}
    .bar {{ height: 14px; background: #e2e8f0; border-radius: 8px; overflow: hidden; }}
    .bar i {{ display: block; height: 100%; background: linear-gradient(90deg, #0284c7, #38bdf8); border-radius: 8px; }}
    .scenario-bear {{ color: var(--red); font-weight: 750; }}
    .scenario-base {{ color: var(--palantir); font-weight: 750; }}
    .scenario-bull {{ color: var(--green); font-weight: 750; }}
    ul {{ padding-left: 22px; margin: 10px 0; }}
    li {{ margin: .5rem 0; color: #334155; }}
    .decision {{ font-size: 1.05rem; margin-bottom: 14px; line-height: 1.6; }}
    .img-box {{ text-align: center; margin: 24px 0; }}
    .img-box img {{ max-width: 100%; height: auto; border-radius: 8px; border: 1px solid var(--line); box-shadow: var(--shadow); }}
    .footer {{ color: var(--muted); font-size: .82rem; padding: 16px 4px 40px; border-top: 1px solid var(--line); margin-top: 30px; }}
    .badge-quant {{ background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: .75rem; font-weight: 700; display: inline-block; }}
    @media(max-width: 860px) {{
      .wrap {{ padding: 16px; }}
      header, section {{ padding: 20px; }}
      .kpis, .two, .three, .four {{ grid-template-columns: 1fr; }}
      .barrow {{ grid-template-columns: 120px 1fr 80px; }}
      table {{ font-size: .82rem; }}
      th, td {{ padding: 8px 6px; }}
    }}
  </style>
</head>
<body>
<main class="wrap">
  <header>
    <div class="eyebrow">Pesquisa de ações • Laboratório iitauquant • revisão de 24/09/2026</div>
    <h1>Palantir (P2LT34 / PLTR): forte crescimento, preço e risco ainda importam</h1>
    <p class="meta">Data-base preservada: 24/09/2026 • Nasdaq: PLTR / B3: P2LT34 • 3 BDRs = 1 ação • horizonte analítico: 12–24 meses</p>
    <div class="verdict"><strong>Postura: aprofundar valuation antes de uma decisão de compra.</strong><br>
      O 2T26 confirma crescimento de receita de 93% e margem operacional GAAP de 47,1%. Isso sustenta a tese operacional, mas não estabelece preço justo nem elimina perdas. Os valores de posição abaixo são uma ilustração histórica bruta, sem comprovação de execução. Stops não garantem preço de venda, lucro ou perda máxima.</div>
  </header>

  <div class="callout"><strong>Revisão e procedência:</strong> esta edição corrige narrativa, fórmulas e fontes; não refaz o backtest, não atualiza os dados de pesquisa e não certifica preços executáveis. O arquivo local tem data de 24/09/2026, mas não registra horário/fuso de coleta nem comprova fechamento definitivo. Seus campos chamados <code>close</code> são tratados aqui como <strong>snapshot histórico de horário desconhecido</strong>; a barra do próprio dia pode estar incompleta. Métricas e gráficos que a utilizam são preliminares.</div>
  <div class="grid kpis">
    <div class="kpi highlight"><b>+{br(paper_return)}%</b><span>Variação bruta ilustrativa: R$ {br(entry)} → R$ {br(bdr)}; não realizada</span></div>
    <div class="kpi"><b>US$ {br(us_price)}</b><span>PLTR (Nasdaq), snapshot local de 24/09; horário não documentado</span></div>
    <div class="kpi"><b>R$ {br(bdr)}</b><span>P2LT34, snapshot local; paridade calculada R$ {br(parity)}</span></div>
    <div class="kpi"><b>R$ {br(stop20)}</b><span>Gatilho ilustrativo: snapshot − 2 × ATR; execução não garantida</span></div>
  </div>

  <section>
    <h2>1. Exemplo histórico de posição: cálculo, não instrução de negociação</h2>
    <div class="user-card"><h3>Referência de entrada de R$ {br(entry)}</h3><p>A diferença até R$ {br(bdr)} é R$ {br(bdr-entry)} por BDR, ou {br(paper_return)}%, antes de corretagem, emolumentos, impostos e eventual slippage. A valorização marcada no snapshot não comprova lucro realizado nem confirma que uma ordem do investidor foi executada.</p></div>
    <div class="grid three">
      <div class="card neutral"><span class="tag">Sinal histórico</span><h3>Proximidade não comprova eficácia</h3><p>O relatório original associou a referência de entrada ao sinal de 21/09/2026, a R$ 307,10. O log de execução não foi revalidado nesta revisão. A coincidência com um sinal não caracteriza ponto ótimo nem prova fluxo institucional.</p></div>
      <div class="card neutral"><span class="tag">Volatilidade</span><h3>ATR é uma medida histórica</h3><p>O snapshot registra ATR14 de R$ {br(atr)}. O ganho ilustrativo corresponde a {br((bdr-entry)/atr)} ATR, abaixo de 2,5 ATR. Essa relação não define, por si só, uma regra ótima de saída.</p></div>
      <div class="card neutral"><span class="tag">Nível de referência</span><h3>Máxima anterior não é preço justo</h3><p>R$ 373,83 é o nível histórico citado na edição original, sem data da observação revalidada. Sua distância do snapshot é {br((373.83/bdr-1)*100)}%; não há garantia de retorno a esse nível.</p></div>
    </div>
    <h3>Comparação ilustrativa de gatilhos</h3>
    <div style="overflow-x:auto"><table><thead><tr><th>Regra aritmética</th><th>Gatilho</th><th>Variação bruta se executado exatamente no gatilho</th><th>Limitação</th></tr></thead><tbody>
      <tr><td>Snapshot − 2,0 × ATR</td><td>R$ {br(stop20)}</td><td>+{br((stop20/entry-1)*100)}% / R$ {br(stop20-entry)}</td><td>Gaps, leilões e liquidez podem levar a execução abaixo do gatilho; não assegura lucro líquido.</td></tr>
      <tr><td>Snapshot − 2,5 × ATR</td><td>R$ {br(stop25)}</td><td>{br((stop25/entry-1)*100)}% / R$ {br(stop25-entry)}</td><td>Usa o multiplicador descrito no backtest; isso não comprova adequação à posição.</td></tr>
      <tr><td>Referência de entrada</td><td>R$ {br(entry)}</td><td>0,00% antes dos custos</td><td>Execução no preço de entrada ainda pode gerar perda líquida; stop limitado pode não executar.</td></tr>
    </tbody></table></div>
    <p class="small">São níveis estáticos calculados sobre um snapshot. Um trailing stop exige regra de atualização definida e suporte da corretora. <a href="https://www.finra.org/investors/insights/stop-orders-factors-consider-during-volatile-markets">FINRA: riscos de execução de ordens stop</a>.</p>
  </section>

  <section>
    <h2>2. Gráfico histórico preservado</h2>
    <p>A imagem original foi preservada sem reprocessar dados. Suas faixas e rótulos de compra, alvos, proteção ou lucro são anotações do exercício original, não ordens nem evidência de execução. Não existe comprovação de venda realizada.</p>
    <div class="img-box"><img src="data:image/png;base64,{b64_trade_setup}" alt="Gráfico histórico P2LT34 com níveis ilustrativos, sem garantia de execução" /><p class="small">Figura 1: gráfico original, março–setembro de 2026. A faixa de valorização representa ganho bruto hipotético/não realizado. A última barra pode estar incompleta.</p></div>
  </section>

  <section>
    <h2>3. Fundamentos: expansão real, expectativas elevadas</h2>
    <div class="grid two">
      <div class="card positive"><span class="tag">Produto</span><h3>Integração de dados e IA</h3><p>Foundry, Gotham, Apollo e AIP integram análise e operações de clientes. A tese é que adoção e expansão dos contratos sustentem crescimento; não há evidência aqui de monopólio, demanda inelástica ou superioridade incontestável frente aos concorrentes.</p></div>
      <div class="card positive"><span class="tag">Receita comercial</span><h3>EUA: US$ 764 milhões no 2T26</h3><p>A companhia reportou crescimento de 149% nessa linha. O ritmo é forte, mas sua manutenção depende de novas vendas, expansão e retenção de clientes. Crescimento passado não garante crescimento futuro. <a href="https://investors.palantir.com/reports-2026.html">Divulgação de 03/08/2026</a>.</p></div>
      <div class="card neutral"><span class="tag">Governo</span><h3>Contrato não equivale a receita garantida</h3><p>O 10-Q permite distinguir receita reconhecida, compromissos e opções: vários contratos podem ser encerrados por conveniência. Os valores de contratos de setembro/Maven citados antes foram retirados da tese quantitativa por falta de ligação primária específica validada nesta revisão.</p></div>
      <div class="card neutral"><span class="tag">Liquidez</span><h3>Caixa e títulos: US$ 9,409 bilhões</h3><p>Em 30/06/2026, a companhia não tinha saldo utilizado na linha de crédito. Os US$ 211,4 milhões são passivos não circulantes de arrendamento operacional, não dívida bancária total. A liquidez reduz risco de financiamento, mas não protege o preço da ação.</p></div>
    </div>
  </section>

  <section>
    <h2>4. Demonstrações financeiras: períodos e definições reconciliados</h2>
    <div style="overflow-x:auto"><table><thead><tr><th>Métrica</th><th>Período e valor</th><th>Comparação / leitura</th></tr></thead><tbody>
      <tr><td>Receita consolidada</td><td>2T26: US$ 1,935 bi</td><td>+92,8% a/a, arredondado para 93% pela companhia.</td></tr>
      <tr><td>Receita comercial / governamental EUA</td><td>2T26: US$ 764 mi / US$ 809 mi</td><td>+149% / +90% a/a conforme divulgação de resultados; não representa margem por produto.</td></tr>
      <tr><td>Margem bruta GAAP</td><td>2T26: {br(gross_margin,1)}%</td><td>2T25: {br(prior_gross_margin,1)}%; aumento de aproximadamente {br((gross_margin-prior_gross_margin)*100,0)} pontos-base.</td></tr>
      <tr><td>Margem operacional GAAP</td><td>2T26: {br(operating_margin,1)}%</td><td>2T25: {br(prior_operating_margin,1)}%; aumento de aproximadamente {br((operating_margin-prior_operating_margin)*100,0)} pontos-base.</td></tr>
      <tr><td>Lucro atribuível aos acionistas</td><td>2T26: US$ 1,062 bi</td><td>Margem de {br(net_margin,1)}%. Resultado inclui receitas financeiras e outros ganhos; não extrapolar essa margem mecanicamente.</td></tr>
      <tr><td>Caixa operacional / capex</td><td>1S26: US$ 2,115 bi / US$ 0,022 bi</td><td>FCF simples calculado: US$ {br(fcf_h1,3)} bi no semestre. Não é TTM nem FCF ajustado divulgado pela companhia.</td></tr>
      <tr><td>Caixa, equivalentes e títulos negociáveis</td><td>30/06/2026: US$ 9,409 bi</td><td>Somatório de US$ 2,030 bi e US$ 7,379 bi. Não equivale a patrimônio líquido ou ausência de obrigações.</td></tr>
    </tbody></table></div>
    <p class="small">Fonte: <a href="https://investors.palantir.com/files/2026%20Q2%20PLTR%2010-Q.pdf">10-Q do trimestre encerrado em 30/06/2026, divulgado em 03/08/2026, pp. 3–4, 8, 13 e 17</a>. Demonstrações trimestrais não auditadas. Margens calculadas a partir dos valores sem arredondamento.</p>
    <div class="callout"><strong>Qualidade do resultado:</strong> no 2T26, juros geraram US$ 77,5 mi, outros resultados US$ 91,8 mi e despesa tributária US$ 15,4 mi sobre lucro antes de impostos de US$ 1,081 bi (taxa efetiva ~1,4%). A remuneração em ações foi US$ 265,2 mi: entra no lucro GAAP, é adicionada de volta no fluxo operacional e pode diluir acionistas. Caixa forte não dispensa atenção à recorrência do lucro.</div>
  </section>

  <section>
    <h2>5. Valuation e limites dos modelos do laboratório</h2>
    <div class="grid three">
      <div class="card amber"><span class="tag">Valuation</span><h3>Múltiplos precisam de denominador</h3><p>As referências originais a P/L projetado de 83x e P/S de 75x não tinham data, provedor e período reconciliados. Foram retiradas da conclusão. Não há preço justo validado ou margem de segurança demonstrada neste relatório.</p></div>
      <div class="card neutral"><span class="tag">Fatores e momentum</span><h3>Ranking não validado</h3><p>Não foi demonstrado percentil 99 nem liderança do universo. O snapshot registra momentum 12–1 PLTR de {br(user_data['momentum_12_1_pltr_pct'])}%, sem universo comparável validado. O sinal ATR de 20 barras é outro indicador e não comprova liderança no ranking 12–1.</p></div>
      <div class="card negative"><span class="tag">Overlay</span><h3>SHADOW: desligado para capital</h3><p>O <a href="AAKR.html">relatório AAKR/LASTRO</a> informa que o overlay falhou no teste com dados disponíveis à época. Stock-picking não foi validado. O mecanismo não deve ser descrito como proteção automática ou garantia de diversificação.</p></div>
    </div>
    <p>Uma empresa pode crescer e sua ação cair se o mercado reduzir o múltiplo pago. Antes de inferir retorno, é necessário atualizar cotação e estimativas com a mesma data, distinguir EPS GAAP de ajustado e testar desaceleração, diluição e compressão de múltiplos.</p>
  </section>

  <section>
    <h2>6. Backtest histórico preservado: Momentum ATR versus buy &amp; hold</h2>
    <p>Resultados herdados da pesquisa original de 2020–2026, <strong>não reexecutados e não auditados nesta revisão</strong>. Configuração descrita no relatório original: momentum de 20 barras, ATR14, stop 2,5 × ATR, custo de 15 bps por lado e execução no Open de t+1. Não foram revalidados integridade dos preços, janelas por ativo, tratamento de caixa, slippage ou robustez fora da amostra.</p>
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>Ativo / Ticker</th>
          <th>Barras</th>
          <th>Trades</th>
          <th>Win Rate</th>
          <th>Retorno Mom ATR</th>
          <th>CAGR Mom</th>
          <th>Vol Mom</th>
          <th>Sharpe Mom</th>
          <th>Max DD Mom</th>
          <th>Profit Factor</th>
          <th>Exposição</th>
          <th>Retorno B&H</th>
          <th>Max DD B&H</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#f0f9ff;font-weight:700">
          <td>PLTR (Nasdaq)</td>
          <td>1.503</td>
          <td>67</td>
          <td>41,8%</td>
          <td>+34,73%</td>
          <td>5,12%</td>
          <td>40,1%</td>
          <td>0,321</td>
          <td style="color:var(--red)">-53,49%</td>
          <td>1,35</td>
          <td>36,8%</td>
          <td>+1.940,1%</td>
          <td style="color:var(--red)">-84,62%</td>
        </tr>
        <tr style="background:#fdf4ff;font-weight:700">
          <td>P2LT34.SA (B3)</td>
          <td>1.274</td>
          <td>61</td>
          <td>41,0%</td>
          <td>-10,94%</td>
          <td>-2,26%</td>
          <td>36,4%</td>
          <td>0,116</td>
          <td style="color:var(--red)">-46,51%</td>
          <td>1,09</td>
          <td>32,4%</td>
          <td>+634,32%</td>
          <td style="color:var(--red)">-79,33%</td>
        </tr>
        <tr>
          <td>QQQ (Nasdaq 100)</td>
          <td>1.691</td>
          <td>63</td>
          <td>38,1%</td>
          <td>+34,29%</td>
          <td>4,49%</td>
          <td>12,8%</td>
          <td>0,407</td>
          <td>-21,64%</td>
          <td>1,43</td>
          <td>40,0%</td>
          <td>+243,00%</td>
          <td>-35,62%</td>
        </tr>
        <tr>
          <td>SPY (S&P 500)</td>
          <td>1.691</td>
          <td>71</td>
          <td>40,9%</td>
          <td>+26,88%</td>
          <td>3,61%</td>
          <td>9,8%</td>
          <td>0,410</td>
          <td>-16,12%</td>
          <td>1,45</td>
          <td>45,0%</td>
          <td>+136,46%</td>
          <td>-34,10%</td>
        </tr>
        <tr>
          <td>NVDA (NVIDIA)</td>
          <td>1.691</td>
          <td>83</td>
          <td>38,6%</td>
          <td>+386,05%</td>
          <td>26,57%</td>
          <td>33,2%</td>
          <td>0,874</td>
          <td>-46,74%</td>
          <td>2,05</td>
          <td>47,6%</td>
          <td>+3.638,1%</td>
          <td>-66,36%</td>
        </tr>
        <tr>
          <td>MSFT (Microsoft)</td>
          <td>1.691</td>
          <td>77</td>
          <td>36,4%</td>
          <td>+53,21%</td>
          <td>6,56%</td>
          <td>17,9%</td>
          <td>0,444</td>
          <td>-23,36%</td>
          <td>1,51</td>
          <td>44,4%</td>
          <td>+209,22%</td>
          <td>-37,56%</td>
        </tr>
      </tbody>
    </table>
    </div>
    <div class="img-box"><img src="data:image/png;base64,{b64_equity_drawdown}" alt="Curva histórica de patrimônio e drawdown, preservada sem reexecução" /><p class="small">Figura 2: imagem original do experimento; não é trajetória de capital real nem previsão.</p></div>
    <div class="callout"><strong>Leitura dos números preservados:</strong><ul>
      <li>No BDR, o sistema registrou retorno de −10,94%, CAGR de −2,26% e queda máxima de −46,51%. Isso não sustenta uma afirmação de eficácia de compra ou proteção integral.</li>
      <li>Em PLTR, o drawdown registrado do sistema (−53,49%) foi menor que no buy &amp; hold (−84,62%), mas continuou severo; o retorno acumulado foi muito menor. Uma amostra histórica não demonstra superioridade futura.</li>
      <li>Exposição de 36,8% em PLTR não comprova remuneração do restante do tempo por CDI. BIL é um instrumento em dólares; CDI é uma referência em reais. Não foram adicionados juros hipotéticos ao resultado original.</li>
      <li>Janelas diferentes, seleção posterior dos ativos e custos reais limitam a comparação. A tabela não é ranking de estratégias prontas para capital.</li>
    </ul></div>
  </section>

  <section>
    <h2>7. BDR: paridade aritmética e risco cambial</h2>
    <div class="grid two">
      <div class="card neutral"><h3>3 BDRs para 1 ação</h3><p>O <a href="https://finservices.b3.com.br/documents/823983/1006460/Programa_BRP2LTBDR001.pdf/514d74d7-b525-3f62-121f-9abec804de55">programa P2LT34 do Banco B3</a> identifica paridade BDR:ação de 3:1. Banco B3 é o depositário do programa.</p><p>Paridade simplificada = PLTR × USD/BRL ÷ 3. No snapshot: US$ {br(us_price)} × {br(fx,4)} ÷ 3 = <strong>R$ {br(parity)}</strong>; desvio de {br(spread)}% frente a R$ {br(bdr)}. Preços sem horário sincronizado não demonstram arbitragem nem spread executável.</p></div>
      <div class="card neutral"><h3>Câmbio pode ajudar ou prejudicar</h3><p>Antes de custos, mantendo a proporção do programa, retorno aproximado em reais = (1 + retorno PLTR em US$) × (1 + variação USD/BRL) − 1. Ação +10% e dólar −10% resultam em −1%, não em proteção integral.</p><p>Taxas, impostos, liquidez, bid–ask e eventos do programa afetam o retorno do BDR. A cotação é preço de mercado; paridade não é avaliação econômica da empresa.</p></div>
    </div>
  </section>

  <section id="cenarios">
    <h2>8. Sensibilidade de preço e câmbio para 12–24 meses</h2>
    <p>Hipóteses de preço preservadas para ilustrar sensibilidade, sem probabilidades calibradas, consenso confirmado ou modelo que as transforme em preço-alvo. O retorno de uma compra nova deve usar seu preço de execução, e não a referência histórica de R$ {br(entry)}.</p>
    <div style="overflow-x:auto"><table><thead><tr><th>Hipótese</th><th>PLTR (US$)</th><th>USD/BRL</th><th>BDR pela paridade</th><th>vs. R$ {br(entry)}</th><th>vs. snapshot R$ {br(bdr)}</th></tr></thead><tbody>
      <tr><td class="scenario-bear">Baixista</td><td>125,00</td><td>4,90</td><td>R$ {br(125*4.9/ratio)}</td><td>{br((125*4.9/ratio/entry-1)*100,1)}%</td><td>{br((125*4.9/ratio/bdr-1)*100,1)}%</td></tr>
      <tr><td class="scenario-base">Intermediária</td><td>215,00</td><td>5,20</td><td>R$ {br(215*5.2/ratio)}</td><td>+{br((215*5.2/ratio/entry-1)*100,1)}%</td><td>+{br((215*5.2/ratio/bdr-1)*100,1)}%</td></tr>
      <tr><td class="scenario-bull">Otimista</td><td>265,00</td><td>5,40</td><td>R$ {br(265*5.4/ratio)}</td><td>+{br((265*5.4/ratio/entry-1)*100,1)}%</td><td>+{br((265*5.4/ratio/bdr-1)*100,1)}%</td></tr>
    </tbody></table></div>
    <p class="small">Variações de preço antes de custos e impostos, sem dividendos. Não há piso de perda na linha baixista: perdas maiores são possíveis. Uma ordem stop não limita garantidamente esse resultado.</p>
  </section>

  <section>
    <h2>9. Evidências a acompanhar</h2>
    <div class="grid two">
      <div class="card positive"><h3>O que fortalece a tese operacional</h3><ul><li>Expansão de clientes e receita comercial convertida em caixa.</li><li>Crescimento governamental sustentado por receita reconhecida e opções efetivamente exercidas.</li><li>Margens operacionais e geração de caixa sustentáveis após remuneração em ações e impostos normalizados.</li></ul></div>
      <div class="card negative"><h3>O que exige reavaliação</h3><ul><li>Desaceleração, cancelamentos, competição ou menores orçamentos dos clientes.</li><li>Diluição ou resultado financeiro mascarando enfraquecimento operacional.</li><li>Compressão de múltiplos, mesmo com lucro crescente. Rompimentos de médias móveis não comprovam nem refutam sozinhos a tese fundamentalista.</li></ul></div>
    </div>
  </section>

  <section>
    <h2>10. Critérios antes de usar capital</h2>
    <div class="grid three">
      <div class="card neutral"><span class="tag">Preço</span><h3>Atualizar a evidência</h3><p>Comparar cotação, spread, câmbio e estimativas de lucro com horários e definições claros. Este snapshot não fornece ordem pronta.</p></div>
      <div class="card neutral"><span class="tag">Risco</span><h3>Dimensionamento depende da carteira</h3><p>Horizonte, liquidez necessária, perdas toleráveis e exposição conjunta a IA, tecnologia e dólar importam. Uma faixa fixa de 5%–8% não foi validada e não garante descorrelação.</p></div>
      <div class="card amber"><span class="tag">Execução</span><h3>Entender o tipo de ordem</h3><p>Stop a mercado pode vender abaixo do gatilho; stop limitado pode permanecer sem execução. Os níveis ilustrativos deste relatório não substituem uma política de risco definida.</p></div>
    </div>
  </section>

  <section id="fontes">
    <h2>11. Fontes, revisão e limitações</h2>
    <ul class="small">
      <li><a href="https://investors.palantir.com/files/2026%20Q2%20PLTR%2010-Q.pdf">Palantir: 10-Q 2T26</a>, divulgado em 03/08/2026, consultado nesta revisão de 24/09/2026. Período encerrado em 30/06/2026; demonstrações não auditadas, caixa/arrendamentos, remuneração em ações e riscos contratuais.</li>
      <li><a href="https://investors.palantir.com/reports-2026.html">Palantir: divulgação 2T26 e materiais de resultados de 03/08/2026</a>. Dados comerciais publicados pela companhia; projeções não são resultados realizados.</li>
      <li><a href="https://finservices.b3.com.br/documents/823983/1006460/Programa_BRP2LTBDR001.pdf/514d74d7-b525-3f62-121f-9abec804de55">Banco B3: programa BRP2LTBDR001, P2LT34</a>, consultado em 24/09/2026: 3 BDRs por ação, Nasdaq e identificação do depositário. Eventuais mudanças posteriores precisam ser conferidas.</li>
      <li><a href="https://www.finra.org/investors/insights/stop-orders-factors-consider-during-volatile-markets">FINRA: riscos de ordens stop</a>, consultado em 24/09/2026. O gatilho não garante preço de execução.</li>
      <li><a href="../results/palantir_research/user_position_summary.json">Snapshot local de 24/09/2026</a>: preços, ATR e referência de entrada. Sem horário de coleta ou comprovantes de execução; não estabelece posição atual de uma pessoa.</li>
      <li><a href="AAKR.html">AAKR/LASTRO</a>: overlay SHADOW, desligado para capital; seleção individual de ações não validada. Não é proteção implementada nesta posição.</li>
      <li>Backtest e imagens do diretório <code>results/palantir_research</code> preservados. O gerador apenas lê arquivos locais e calcula derivados aritméticos. Não houve atualização dos dados, reexecução ou certificação da estratégia.</li>
    </ul>
    <p class="small">Pesquisa educacional geral; não é recomendação personalizada, ordem de compra/venda, preço-alvo validado ou promessa de rentabilidade. Confiança alta nas demonstrações citadas; limitada para snapshot, sinal, comparabilidade do backtest e valuation.</p>
  </section>
  <div class="footer">Data-base e revisão editorial: 24/09/2026 • iitauquant • Valores arredondados. Fontes históricas preservadas, sem atualização automática de preços.</div>
</main>
</body>
</html>
"""

report_file = RELATORIOS_DIR / "palantir_p2lt34_analise_2026-09-24.html"
report_file.write_text(html_content, encoding="utf-8")
print(f"Relatório histórico renderizado offline: {report_file}")
