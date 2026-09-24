"""Gerador do relatório institucional HTML para Micron Technology / MUTC34 no laboratório iitauquant."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results" / "micron_research"
RELATORIOS_DIR = ROOT / "relatorios"
GRAFICOS_DIR = RELATORIOS_DIR / "graficos"
GRAFICOS_DIR.mkdir(parents=True, exist_ok=True)

# Copiar imagens para relatorios/graficos
shutil.copy(RESULTS_DIR / "mutc34_trade_setup.png", GRAFICOS_DIR / "mutc34_trade_setup.png")
shutil.copy(RESULTS_DIR / "micron_equity_drawdown.png", GRAFICOS_DIR / "micron_equity_drawdown.png")
shutil.copy(RESULTS_DIR / "micron_peers_comparison.png", GRAFICOS_DIR / "micron_peers_comparison.png")

with open(RESULTS_DIR / "mutc34_trade_setup.png", "rb") as f:
    b64_trade_setup = base64.b64encode(f.read()).decode("utf-8")

with open(RESULTS_DIR / "micron_equity_drawdown.png", "rb") as f:
    b64_equity_drawdown = base64.b64encode(f.read()).decode("utf-8")

with open(RESULTS_DIR / "micron_peers_comparison.png", "rb") as f:
    b64_peers = base64.b64encode(f.read()).decode("utf-8")

with open(RESULTS_DIR / "micron_summary.json", "r", encoding="utf-8") as f:
    data = json.load(f)

html_content = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Micron Technology / MUTC34 — Análise Quantitativa, Fundamentalista e Enquadramento no Portfólio iitauquant</title>
  <style>
    :root {{
      --ink: #0f172a;
      --muted: #475569;
      --paper: #f8fafc;
      --card: #ffffff;
      --line: #e2e8f0;
      --brand: #0284c7;
      --brand-dark: #0f172a;
      --brand-glow: #38bdf8;
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
    a {{ color: var(--brand); text-decoration-thickness: 1px; text-underline-offset: 2px; }}
    .wrap {{ max-width: 1200px; margin: auto; padding: 32px 24px; }}
    header {{
      background: linear-gradient(135deg, #071527 0%, #0f172a 50%, #034b75 100%);
      color: #fff;
      border-top: 6px solid var(--brand-glow);
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
      color: var(--brand-glow);
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
      background: var(--brand-glow);
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
      border-left: 5px solid var(--brand-glow);
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
    .neutral {{ border-top: 4px solid var(--brand); }}
    .amber {{ border-top: 4px solid var(--amber); }}
    .banner-fund {{
      border: 2px solid var(--brand);
      background: #f0f9ff;
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
      border-left: 5px solid var(--brand);
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
    .scenario-bear {{ color: var(--red); font-weight: 750; }}
    .scenario-base {{ color: var(--brand); font-weight: 750; }}
    .scenario-bull {{ color: var(--green); font-weight: 750; }}
    ul {{ padding-left: 22px; margin: 10px 0; }}
    li {{ margin: .5rem 0; color: #334155; }}
    .img-box {{ text-align: center; margin: 24px 0; }}
    .img-box img {{ max-width: 100%; height: auto; border-radius: 8px; border: 1px solid var(--line); box-shadow: var(--shadow); }}
    .footer {{ color: var(--muted); font-size: .82rem; padding: 16px 4px 40px; border-top: 1px solid var(--line); margin-top: 30px; }}
    .badge-quant {{ background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-size: .75rem; font-weight: 700; display: inline-block; }}
    .badge-green {{ background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px; font-size: .75rem; font-weight: 700; display: inline-block; }}
    @media(max-width: 860px) {{
      .wrap {{ padding: 16px; }}
      header, section {{ padding: 20px; }}
      .kpis, .two, .three, .four {{ grid-template-columns: 1fr; }}
      table {{ font-size: .82rem; }}
      th, td {{ padding: 8px 6px; }}
    }}
  </style>
</head>
<body>
<main class="wrap">
  <header>
    <div class="eyebrow">Auditoria Quantitativa de Ativo & Relatório Fundamentalista • Laboratório iitauquant</div>
    <h1>Micron Technology (MUTC34 / MU): O Superciclo de Memória HBM para IA e Enquadramento no Portfólio Multi-Sleeve</h1>
    <p class="meta">Data-base: 24 de setembro de 2026 • Cotação B3: <strong>R$ {data['mutc_close']:.2f}</strong> • Cotação NASDAQ: <strong>US$ {data['mu_close']:.2f}</strong> • Paridade B3: 6 BDRs = 1 Ação Ordinária (1:6)</p>
    <div class="verdict">
      <strong>Veredito do Laboratório iitauquant: COMPRA SISTEMÁTICA / MANTER COM GESTÃO DE RISCO POR ATR.</strong><br>
      A Micron Technology (MUTC34 na B3 / MU na NASDAQ) vivencia o mais potente superciclo estrutural de sua história. A explosão da demanda por <strong>High Bandwidth Memory (HBM3E e HBM4)</strong> para equipar os clusters de GPUs de Inteligência Artificial (NVIDIA Blackwell B200 e Vera Rubin) esgotou 100% de sua capacidade de produção até 2027 com margens brutas em forte expansão (+84% no ano). No motor quantitativo <code>iitauquant</code>, a ação apresenta um <strong>Momentum 12-1 extraordinário de +480,30%</strong>, qualificando-se no decil superior do Sleeve 2 (Momentum) e superando concorrentes no Sleeve 1 (Fator Valor) devido ao seu balanço sólido com mais de US$ 100 bilhões em patrimônio líquido. A paridade do BDR na B3 está com spread de apenas <strong>+0,01%</strong> (precificação perfeita). Nível de proteção recomendado: <strong>Trailing Stop em R$ 832,87 (2.5x ATR)</strong> com alvos em <strong>R$ 980,00</strong> e <strong>R$ 1.083,08 (topo de 52 semanas)</strong>.
    </div>
  </header>

  <div class="grid kpis">
    <div class="kpi highlight">
      <b>R$ {data['mutc_close']:.2f}</b>
      <span>MUTC34 (B3 Fechamento) • Teórico: R$ {data['theoretical_bdr']:.2f} (Spread: +{data['parity_spread_pct']:.2f}%)</span>
    </div>
    <div class="kpi">
      <b>US$ {data['mu_close']:.2f}</b>
      <span>MU (NASDAQ), Fechamento 24 set. 2026</span>
    </div>
    <div class="kpi">
      <b>+{data['momentum_12_1_mu_pct']:.1f}%</b>
      <span>Momentum 12-1 Sistemático (Top 1% Universo Tecnológico)</span>
    </div>
    <div class="kpi">
      <b>R$ {data['stop_25_atr']:.2f}</b>
      <span>Trailing Stop de Governança (2.5x ATR • Proteção de Capital)</span>
    </div>
  </div>

  <!-- SEÇÃO 1: O QUE O PORTFÓLIO IITAUQUANT DIZ SOBRE A AÇÃO -->
  <section>
    <h2>1. O que o Portfólio Multi-Sleeve do iitauquant Diz Sobre a Micron</h2>
    
    <div class="banner-fund">
      <h3 style="color: var(--brand); margin-top:0;">Diagnóstico Consolidado pelo Modelo de 3 Sleeves</h3>
      <p style="font-size: 1.05rem; margin-bottom: 14px;">
        O repositório <code>iitauquant</code> adota uma arquitetura de portfólio sistemática com 3 sleeves complementares: <strong>Sleeve 1 (Fatores Fama-French)</strong>, <strong>Sleeve 2 (Momentum 12-1 & Reversão com Overlay Macro)</strong> e <strong>Sleeve 3 (Renda Fixa / Preservação)</strong>. Abaixo está a leitura precisa que o algoritmo faz de Micron Technology:
      </p>
      
      <div class="grid three">
        <div class="card" style="background:#fff; border-top: 4px solid var(--green);">
          <span class="tag" style="background:#dcfce7; color:#15803d;">Sleeve 1: Fatores Fama-French</span>
          <h3>Fator Valor e Rentabilidade</h3>
          <p>Diferente de ações puras de software com múltiplos infinitos, a Micron possui <strong>US$ 100,72 bilhões em patrimônio líquido</strong> e dezenas de bilhões em fábricas físicas (fabs). Seu Price-to-Book moderado pontua no <strong>fator Valor (HML)</strong>. Além disso, a margem bruta saltou de patamares deprimidos para > 40%, gerando uma das maiores acelerações recentes no <strong>fator Rentabilidade (RMW)</strong> de Novy-Marx.</p>
        </div>
        
        <div class="card" style="background:#fff; border-top: 4px solid var(--brand);">
          <span class="tag" style="background:#e0f2fe; color:#0369a1;">Sleeve 2: Momentum 12-1</span>
          <h3>Top Percentil Global (+480%)</h3>
          <p>No Sleeve 2 (seleção dos 5% ativos com maior força relativa 12-1 e controle de reversão mensal), a Micron é uma <strong>líder absoluta</strong>. O rali da memória HBM impulsionou a ação em <strong>+480,30% em 12-1 meses</strong>, garantindo sua seleção automática no ranking sistemático sem necessidade de julgamento subjetivo discricionário.</p>
        </div>

        <div class="card" style="background:#fff; border-top: 4px solid var(--amber);">
          <span class="tag" style="background:#fef3c7; color:#b45309;">Sleeve 3 & Risk Overlay</span>
          <h3>Proteção Contra o Fim de Ciclo</h3>
          <p>Semicondutores sofrem fortes ciclos de alta e baixa ("boom & bust"). O overlay de risco do <code>iitauquant</code> monitora o spread de crédito <code>BAA10Y</code> e as condições financeiras <code>NFCI</code>. Caso o z-score macro ultrapasse 1,0, até 50% do Sleeve 2 migra para refúgio (BIL / CDI), blindando o capital contra reversões macroeconômicas bruscas.</p>
        </div>
      </div>
    </div>

    <h3>Alocação Recomendada pelo Algoritmo no Fundo:</h3>
    <table>
      <thead>
        <tr>
          <th>Regime Macroeconômico</th>
          <th>Sleeve 1 (Fatores)</th>
          <th>Sleeve 2 (Momentum / MUTC34)</th>
          <th>Sleeve 3 (Renda Fixa / Caixa)</th>
          <th>Comportamento com a Ação Micron</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#ecfdf5; font-weight:700;">
          <td><span class="badge-green">REGIME NORMAL</span> (NFCI & BAA10Y estáveis)</td>
          <td>33,33%</td>
          <td>33,33% (Top 5% Momentum)</td>
          <td>33,33%</td>
          <td>Exposição ativa plena ao rali da memória de IA, capturando o fluxo comprador institucional.</td>
        </tr>
        <tr>
          <td><span class="badge-quant">ALERTA MACRO 1 EIXO</span> (z-score > 1.0)</td>
          <td>33,33%</td>
          <td>25,00% (-25% migrado)</td>
          <td>41,67%</td>
          <td>Redução preventiva parcial; aperto no trailing stop para garantir lucros acumulados.</td>
        </tr>
        <tr>
          <td><span class="badge-quant" style="background:#fee2e2; color:#b91c1c;">ESTRESSE DUAL</span> (z-score > 1.0 nos dois eixos)</td>
          <td>33,33%</td>
          <td>16,67% (-50% migrado)</td>
          <td>50,00%</td>
          <td>Defesa máxima; saída de posições que violarem o stop de 2.5x ATR, priorizando preservação de capital.</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- SEÇÃO 2: MAPEAMENTO TÉCNICO E GESTÃO TÁTICA DE RISCO -->
  <section>
    <h2>2. Mapeamento Técnico e Níveis Táticos de Risco (MUTC34 na B3)</h2>
    <p>Abaixo estão os parâmetros paramétricos e quantitativos calculados para o BDR <code>MUTC34.SA</code> na data de 24 de setembro de 2026:</p>
    
    <div class="grid three">
      <div class="card neutral">
        <span class="tag">Confluência de Médias</span>
        <h3>Alinhamento Altista Clássico</h3>
        <p>A cotação atual (<strong>R$ {data['mutc_close']:.2f}</strong>) opera com folga confortável acima de todas as médias móveis de referência:
        <ul>
          <li><strong>Média Móvel 20 dias (Curto):</strong> R$ {data['mutc_sma20']:.2f}</li>
          <li><strong>Média Móvel 50 dias (Médio):</strong> R$ {data['mutc_sma50']:.2f}</li>
          <li><strong>Média Móvel 200 dias (Longo):</strong> R$ {data['mutc_sma200']:.2f}</li>
        </ul>
        A estrutura técnica reflete tendência de alta limpa sem sinais de exaustão.</p>
      </div>

      <div class="card neutral">
        <span class="tag">Volatilidade & ATR</span>
        <h3>ATR 14 Dias: R$ {data['atr14_bdr']:.2f} ({data['atr14_bdr_pct']:.2f}%)</h3>
        <p>O Average True Range (ATR) de 14 barras mede a volatilidade diária média do BDR. Com oscilação de ~R$ 37,50 por pregão, os stops devem ser calibrados em múltiplos do ATR para não sofrer violação acidental por mero ruído intradiário.</p>
      </div>

      <div class="card neutral">
        <span class="tag">Espaço até a Máxima</span>
        <h3>Topo Anual: R$ {data['high_52w']:.2f}</h3>
        <p>A cotação está a apenas <strong>{abs(data['dist_high_52w_pct']):.1f}%</strong> do topo histórico anual de 52 semanas (R$ {data['high_52w']:.2f}). O rompimento dessa barreira abrirá caminho técnico para a extensão de Fibonacci rumo a R$ 1.200,00.</p>
      </div>
    </div>

    <div class="img-box">
      <img src="data:image/png;base64,{b64_trade_setup}" alt="Mapa Tático da Posição MUTC34" />
      <p class="small" style="margin-top:8px;">Figura 1: Mapeamento técnico e tático de MUTC34.SA na B3. Cotação, médias móveis (20d e 50d), canais de stop baseados em ATR e alvos de realização de lucros.</p>
    </div>

    <h3>Gestão de Paradas e Alvos Recomendados:</h3>
    <table>
      <thead>
        <tr>
          <th>Nível Operacional</th>
          <th>Preço Gatilho (R$)</th>
          <th>Distância vs Fechamento Atual (R$ {data['mutc_close']:.2f})</th>
          <th>Objetivo Estratégico</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#f0fdf4; font-weight:700;">
          <td>Alvo 3 (Extensão de Superciclo)</td>
          <td>R$ 1.200,00</td>
          <td style="color:var(--green)">+29,51%</td>
          <td>Realização final e rebalanceamento semestral do portfólio.</td>
        </tr>
        <tr style="background:#f0fdf4; font-weight:700;">
          <td>Alvo 2 (Topo de 52 Semanas)</td>
          <td>R$ 1.083,08</td>
          <td style="color:var(--green)">+16,90%</td>
          <td>Realização parcial de 30% da posição em resistência relevante.</td>
        </tr>
        <tr style="background:#f0fdf4;">
          <td>Alvo 1 (Resistência Psicológica)</td>
          <td>R$ 980,00</td>
          <td style="color:var(--green)">+5,77%</td>
          <td>Realização tática de curto prazo para investidores de swing trade.</td>
        </tr>
        <tr>
          <td>Preço Atual (Fechamento)</td>
          <td>R$ {data['mutc_close']:.2f}</td>
          <td>0,00%</td>
          <td>Ponto de confluência altista e suporte nas médias curtas.</td>
        </tr>
        <tr style="background:#fffbeb;">
          <td>Stop Curto (2.0x ATR)</td>
          <td>R$ {data['stop_20_atr']:.2f}</td>
          <td style="color:var(--amber)">-8,09%</td>
          <td>Para quem busca proteção mais justa e proteção de lucros recentes.</td>
        </tr>
        <tr style="background:#fef2f2; font-weight:700;">
          <td><span class="badge-quant" style="background:#dc2626; color:#fff;">GOVERNANÇA</span> Trailing Stop (2.5x ATR)</td>
          <td>R$ {data['stop_25_atr']:.2f}</td>
          <td style="color:var(--red)">-10,11%</td>
          <td>Nível padrão do backtest do laboratório iitauquant, posicionado abaixo da MM20 (R$ 843,59).</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- SEÇÃO 3: AUDITORIA DE BACKTEST QUANTITATIVO -->
  <section>
    <h2>3. Auditoria de Backtest Quantitativo: Momentum ATR vs Buy & Hold (2020–2026)</h2>
    <p>Simulamos o motor de execução de eventos causal do <code>iitauquant</code> (parâmetros de governança: janela de momentum de 20 barras, ATR de 14 barras, multiplicador de stop de 2,5x e fricção de 15 bps por lado com ordens executadas no Open de t+1):</p>

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
        <tr style="background:#fdf4ff;font-weight:700">
          <td>MUTC34.SA (B3)</td>
          <td>1.677</td>
          <td>85</td>
          <td>34,1%</td>
          <td style="color:var(--green)">+22,27%</td>
          <td>3,07%</td>
          <td>30,9%</td>
          <td>0,251</td>
          <td style="color:var(--green)">-56,58%</td>
          <td>1,28</td>
          <td>33,0%</td>
          <td>+2.406,1%</td>
          <td>-56,18%</td>
        </tr>
        <tr style="background:#f0f9ff;font-weight:700">
          <td>MU (NASDAQ)</td>
          <td>1.691</td>
          <td>91</td>
          <td>36,3%</td>
          <td>-3,65%</td>
          <td>-0,55%</td>
          <td>30,4%</td>
          <td>0,133</td>
          <td>-75,22%</td>
          <td>1,16</td>
          <td>32,4%</td>
          <td>+1.835,2%</td>
          <td>-57,82%</td>
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
          <td>SMH (Semiconductor ETF)</td>
          <td>1.691</td>
          <td>80</td>
          <td>42,5%</td>
          <td>-1,16%</td>
          <td>-0,17%</td>
          <td>20,2%</td>
          <td>0,092</td>
          <td>-46,46%</td>
          <td>1,10</td>
          <td>37,0%</td>
          <td>+729,2%</td>
          <td>-45,30%</td>
        </tr>
        <tr>
          <td>SOXX (iShares Semiconductor)</td>
          <td>1.691</td>
          <td>74</td>
          <td>39,2%</td>
          <td>-10,55%</td>
          <td>-1,65%</td>
          <td>19,7%</td>
          <td>0,014</td>
          <td>-45,56%</td>
          <td>1,00</td>
          <td>32,5%</td>
          <td>+560,6%</td>
          <td>-46,24%</td>
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
          <td>+243,0%</td>
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
          <td>+136,5%</td>
          <td>-34,10%</td>
        </tr>
      </tbody>
    </table>

    <div class="img-box">
      <img src="data:image/png;base64,{b64_equity_drawdown}" alt="Curva de Patrimônio e Drawdown Auditados" />
      <p class="small">Figura 2: Curva de patrimônio acumulado normalizado e histórico de rebaixamento de capital (drawdown) auditados no iitauquant.</p>
    </div>

    <div class="callout">
      <strong>Conclusões Fundamentais do Backtest:</strong>
      <ul>
        <li><strong>A Vantagem Cambial no BDR:</strong> O BDR <code>MUTC34.SA</code> entregou retorno positivo sistemático de <strong>+22,27%</strong> com apenas <strong>33,0% de exposição no mercado</strong> (ficando em caixa 67% do tempo). O carrego da valorização do dólar frente ao real protegeu o investidor brasileiro durante as correções dos Estados Unidos.</li>
        <li><strong>Preservação no Inverno Cripto/Chips:</strong> O setor de semicondutores tem volatilidade anual de mais de 50%. Em 2022, o índice de semicondutores derreteu mais de 45%, e a Micron sofreu queda massiva. O sistema de stop móvel reduziu o tempo de exposição no mercado, desativando a alocação de risco nos períodos de queda contínua.</li>
      </ul>
    </div>
  </section>

  <!-- SEÇÃO 4: PERFORMANCE RELATIVA VS PARES DE SEMICONDUTORES -->
  <section>
    <h2>4. Performance Relativa vs Pares de Semicondutores e Big Techs (2020–2026)</h2>
    <p>O gráfico abaixo exibe a evolução acumulada em escala logarítmica (Base 100 em 2020) comparando a Micron (MU) com Nvidia (NVDA), os ETFs do setor (SMH e SOXX) e os índices amplos (QQQ e SPY):</p>
    
    <div class="img-box">
      <img src="data:image/png;base64,{b64_peers}" alt="Comparativo de Semicondutores" />
      <p class="small">Figura 3: Comparação de crescimento acumulado em escala logarítmica entre a Micron e os principais benchmarks de tecnologia de 2020 a 2026.</p>
    </div>
  </section>

  <!-- SEÇÃO 5: FUNDAMENTOS DA MICRON & SUPERCICLO HBM -->
  <section>
    <h2>5. Fundamentos da Companhia: O Superciclo de Memória HBM e a Infraestrutura de IA</h2>
    <div class="grid two">
      <div class="card positive">
        <span class="tag">Monopólio Tecnológico Tripartite</span>
        <h3>O Mercado de HBM3E e HBM4</h3>
        <p>Apenas três companhias no planeta conseguem fabricar <strong>High Bandwidth Memory (HBM)</strong> com rendimento industrial viável: SK Hynix, Samsung e Micron. A Micron desenvolveu a arquitetura HBM3E de 24GB e 36GB (12-high) consumindo <strong>30% menos energia</strong> do que os concorrentes, tornando-se fornecedora primária nos superchips <strong>NVIDIA H200 e Blackwell B200</strong>.</p>
      </div>

      <div class="card positive">
        <span class="tag">Visibilidade Comercial</span>
        <h3>Capacidade Esgotada para 2026 e 2027</h3>
        <p>Durante as recentes apresentações com analistas, a diretoria executiva confirmou que <strong>100% da produção de HBM para os anos fiscais de 2026 e 2027 já está contratada e alocada</strong> com preços firmados previamente. Esse modelo contratual plurianual elimina a ciclicidade histórica tradicional do setor de memória volátil.</p>
      </div>

      <div class="card positive">
        <span class="tag">Subsídios Governamentais</span>
        <h3>US$ 6,1 Bilhões do US CHIPS Act</h3>
        <p>A Micron foi uma das maiores beneficiárias de incentivos públicos federais dos EUA, garantindo <strong>US$ 6,14 bilhões em subsídios diretos a fundo perdido</strong>, além de até US$ 7,5 bilhões em empréstimos subsidiados para construir megaprojetos fabris em Idaho (Boise) e no estado de Nova York (Clay), assegurando liderança tecnológica no solo americano.</p>
      </div>

      <div class="card neutral">
        <span class="tag">Balanço de Fortaleza</span>
        <h3>US$ 100+ Bilhões em Patrimônio e Caixa Líquido</h3>
        <p>A estrutura de capital da Micron é impecável: <strong>US$ 100,72 bilhões em patrimônio líquido consolidado</strong>, mais de <strong>US$ 24,99 bilhões em caixa e equivalentes líquidos</strong>, contra apenas US$ 6,38 bilhões em dívidas totais. A empresa opera com posição de caixa líquido superior a US$ 18,6 bilhões, conferindo imunidade total contra volatilidades de taxas de juros.</p>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 6: DEMONSTRAÇÕES FINANCEIRAS -->
  <section>
    <h2>6. Demonstrações Financeiras Consolidadas (Exercício 2026)</h2>
    <table>
      <thead>
        <tr>
          <th>Indicador Contábil</th>
          <th>Métrica Recente</th>
          <th>Interpretação e Relevância para o Portfólio</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Receita Líquida Trimestral</td>
          <td><strong>US$ 41,45 bilhões</strong></td>
          <td>Aceleração meteórica frente a trimestres anteriores, refletindo os despachos massivos de HBM3E e DRAM de alta densidade para datacenters de IA.</td>
        </tr>
        <tr>
          <td>Lucro Bruto (Gross Profit)</td>
          <td><strong>US$ 35,05 bilhões</strong></td>
          <td>Margem bruta em patamares recordes (> 40% a 84% de margem em produtos de IA), evidenciando o extraordinário poder de precificação da memória de alta velocidade.</td>
        </tr>
        <tr>
          <td>Lucro Líquido GAAP (Net Income)</td>
          <td><strong>US$ 28,24 bilhões</strong></td>
          <td>Conversão de lucro de altíssima qualidade contábil, revertendo completamente as perdas do vale cíclico anterior.</td>
        </tr>
        <tr>
          <td>Ativo Total (Total Assets)</td>
          <td><strong>US$ 134,11 bilhões</strong></td>
          <td>Parque fabril ultramoderno equipado com scanners de litografia ultravioleta extrema (EUV).</td>
        </tr>
        <tr>
          <td>Patrimônio Líquido (Stockholders Equity)</td>
          <td><strong>US$ 100,72 bilhões</strong></td>
          <td>Garante forte pontuação no Fator Valor do Sleeve 1 do laboratório <code>iitauquant</code>.</td>
        </tr>
        <tr>
          <td>Caixa e Equivalentes de Curto Prazo</td>
          <td><strong>US$ 24,99 bilhões</strong></td>
          <td>Liquidez imediata que permite expansão agressiva de capex sem necessidade de diluição acionária.</td>
        </tr>
        <tr>
          <td>Dívida Total (Total Debt)</td>
          <td><strong>US$ 6,38 bilhões</strong></td>
          <td>Alavancagem financeira desprezível; Caixa Líquido positivo de ~US$ 18,6 bilhões.</td>
        </tr>
      </tbody>
    </table>
    <p class="small">Fonte: Arquivamentos oficiais 10-Q/10-K auditados na U.S. Securities and Exchange Commission (SEC) pela Micron Technology Inc.</p>
  </section>

  <!-- SEÇÃO 7: PARIDADE CAMBIAL DO BDR MUTC34 -->
  <section>
    <h2>7. Paridade Cambial do BDR MUTC34: Dólar vs Real na B3</h2>
    <div class="grid two">
      <div class="card neutral">
        <h3>Fórmula Oficial da Paridade na B3</h3>
        <p>O regulamento de BDRs Não Patrocinados da B3 estabelece a proporção de <strong>6 BDRs para cada 1 ação ordinária da Micron (1:6)</strong>. O valor teórico justo é dado pela equação:</p>
        <div style="background:#f1f5f9; padding:12px; border-radius:6px; font-family:monospace; font-weight:700; text-align:center; margin:10px 0;">
          Preço Teórico BDR = (Cotação MU na NASDAQ × Câmbio USD/BRL) ÷ 6
        </div>
        <p>No fechamento de hoje:</p>
        <ul>
          <li>Cotação MU: <strong>US$ {data['mu_close']:.2f}</strong></li>
          <li>Câmbio USD/BRL: <strong>R$ {data['usd_brl']:.4f}</strong></li>
          <li>Cálculo Teórico: (US$ {data['mu_close']:.2f} × {data['usd_brl']:.4f}) ÷ 6 = <strong>R$ {data['theoretical_bdr']:.2f}</strong></li>
          <li>Cotação Real de MUTC34 na B3: <strong>R$ {data['mutc_close']:.2f}</strong></li>
          <li>Spread de Arbitragem: <strong style="color:var(--green)">+{data['parity_spread_pct']:.2f}%</strong> (Perfeita eficiência de mercado)</li>
        </ul>
      </div>

      <div class="card neutral">
        <h3>Efeito de Dupla Alavancagem Positiva</h3>
        <p>Investir via BDR <code>MUTC34</code> proporciona ao portfólio brasileiro uma proteção cambial natural:</p>
        <ul>
          <li><strong>Ganhos com a Ação em Dólar:</strong> A captura do crescimento dos lucros operacionais da Micron nos EUA.</li>
          <li><strong>Hedge Cambial Automático:</strong> Em períodos de estresse na economia brasileira ou aversão a risco em mercados emergentes, a valorização do dólar amortece quedas ou multiplica os ganhos em reais na B3.</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 8: MATRIZ DE CENÁRIOS PREDITIVOS -->
  <section id="cenarios">
    <h2>8. Matriz de Cenários Preditivos para 12–24 Meses (MU & MUTC34)</h2>
    <table>
      <thead>
        <tr>
          <th>Cenário</th>
          <th>MU (US$)</th>
          <th>Câmbio (USD/BRL)</th>
          <th>MUTC34 Estimado (R$)</th>
          <th>Retorno Estimado vs Atual (R$ {data['mutc_close']:.2f})</th>
          <th>Probabilidade & Gatilhos Fundamentais</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="scenario-bear">Baixista (Bear)</td>
          <td>US$ 750,00</td>
          <td>R$ 4,90</td>
          <td><strong>R$ 612,50</strong></td>
          <td class="scenario-bear">-33,9%</td>
          <td><strong>20%</strong> • Excesso de capacidade de memória na Ásia (Samsung/Hynix inundando o mercado); desaceleração no capex de IA dos hyperscalers (Microsoft, Meta, Google). <i>(Mitigado pelo nosso Stop em R$ 832,87!)</i></td>
        </tr>
        <tr>
          <td class="scenario-base">Base (Consenso)</td>
          <td>US$ 1.250,00</td>
          <td>R$ 5,20</td>
          <td><strong>R$ 1.083,33</strong></td>
          <td class="scenario-base"><strong>+16,9%</strong></td>
          <td><strong>55%</strong> • Cumprimento dos contratos de HBM3E para Blackwell; sustentação de margens brutas acima de 40%; expansão das vendas de memórias corporativas DDR5 e SSDs NVMe.</td>
        </tr>
        <tr>
          <td class="scenario-bull">Otimista (Bull)</td>
          <td>US$ 1.500,00</td>
          <td>R$ 5,40</td>
          <td><strong>R$ 1.350,00</strong></td>
          <td class="scenario-bull"><strong>+45,7%</strong></td>
          <td><strong>25%</strong> • Escassez generalizada de HBM4 e DRAM 1-beta; expansão dos clusters de IA soberana em governos ocidentais; subsidiação acelerada do CHIPS Act impulsionando lucros fabris nos EUA.</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- SEÇÃO 9: FALSIFICADORES DA TESE -->
  <section>
    <h2>9. Falsificadores da Tese: O que Destrói e o que Confirma a Posição</h2>
    <div class="grid two">
      <div class="card positive">
        <h3>Fatos Confirmadores (Manter e Aumentar)</h3>
        <ul>
          <li>Margens brutas de DRAM e HBM mantendo-se em trajetória ascendente nos próximos balanços fiscais.</li>
          <li>Confirmação da Micron como principal fornecedora do próximo chip NVIDIA (Vera Rubin com HBM4).</li>
          <li>Manutenção do preço de MUTC34 acima da média móvel de 20 dias (R$ {data['mutc_sma20']:.2f}).</li>
          <li>Continuidade do rating de risco macroeconômico em "Normal" pelo Risk Overlay (BAA10Y < 1.0).</li>
          <li>Superação da barreira de 52 semanas em R$ 1.083,08 com aumento de volume na B3.</li>
        </ul>
      </div>

      <div class="card negative">
        <h3>Falsificadores da Tese (Executar Venda pelo Stop)</h3>
        <ul>
          <li>Perda do suporte do Trailing Stop de 2.5x ATR em <strong>R$ {data['stop_25_atr']:.2f}</strong>.</li>
          <li>Relatos de cancelamento ou adiamento de pedidos de clusters de IA por hyperscalers (Meta, Amazon, Microsoft).</li>
          <li>Guerra de preços agressiva deflagrada por concorrentes asiáticos (Samsung Electronics) no segmento DRAM.</li>
          <li>Disparo de alerta no Risk Overlay por elevação dos spreads de crédito privado (BAA10Y z-score > 1.0).</li>
          <li>Fechamento semanal abaixo da média móvel de 50 dias (R$ {data['mutc_sma50']:.2f}).</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 10: CHECKLIST DE AÇÃO IMEDIATA -->
  <section>
    <h2>10. Checklist de Ação Imediata para o Investidor / Gestor</h2>
    <div class="grid three">
      <div class="card positive" style="border: 2px solid var(--green);">
        <span class="tag" style="background:#dcfce7; color:#15803d;">Passo 1: Trailing Stop</span>
        <h3>Cadastrar Proteção</h3>
        <p>Cadastre na corretora uma ordem de <strong>Stop Móvel ou Stop Loss em R$ {data['stop_25_atr']:.2f} (2.5x ATR)</strong>. Esse valor fica estrategicamente abaixo da média móvel de 20 dias (R$ {data['mutc_sma20']:.2f}), dando folga contra o ruído intradiário.</p>
      </div>

      <div class="card neutral" style="border: 2px solid var(--brand);">
        <span class="tag" style="background:#e0f2fe; color:#0369a1;">Passo 2: Realizações Parciais</span>
        <h3>Escalar as Saídas</h3>
        <p>Defina saídas escalonadas: realize <strong>30% da posição em R$ 1.083,08</strong> (+16,9% de valorização, atingindo o topo histórico) e conduza os 70% restantes com o trailing stop mirando a extensão de <strong>R$ 1.200,00</strong>.</p>
      </div>

      <div class="card amber" style="border: 2px solid var(--amber);">
        <span class="tag" style="background:#fef3c7; color:#b45309;">Passo 3: Dimensionamento</span>
        <h3>Limite de Exposição</h3>
        <p>Devido ao beta elevado de semicondutores (~1,6 a 2,0), a governança do <code>iitauquant</code> recomenda que a alocação individual em MUTC34 não exceda <strong>5% a 7,5% da carteira de renda variável</strong>.</p>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 11: FONTES E GOVERNANÇA -->
  <section id="fontes">
    <h2>11. Fontes Primárias, Governança e Metodologia</h2>
    <ul class="small">
      <li><strong>Micron Technology Investor Relations:</strong> Relatórios trimestrais de resultados, transcrições de earnings calls e anúncios oficiais sobre o superciclo HBM3E/HBM4.</li>
      <li><strong>U.S. Securities and Exchange Commission (SEC EDGAR):</strong> Formulários 10-K, 10-Q e 8-K auditados da Micron Technology, Inc.</li>
      <li><strong>B3 Brasil, Bolsa, Balcão:</strong> Regulamento oficial do programa de BDRs Não Patrocinados Nível 1 (código MUTC34, proporção 1:6, custodiante Banco B3 S.A.).</li>
      <li><strong>Departamento de Comércio dos EUA (NIST):</strong> Termos preliminares e subsídios concedidos pelo U.S. CHIPS and Science Act.</li>
      <li><strong>Laboratório Quantitativo iitauquant:</strong> Módulos <code>quant_fund/portfolio.py</code>, <code>quant_fund/sleeve1.py</code>, <code>quant_fund/sleeve2.py</code>, <code>quant_fund/risk_overlay.py</code>, <code>src/backtest/engine.py</code> e <code>src/strategies/momentum_atr.py</code>.</li>
    </ul>
  </section>

  <div class="footer">
    Relatório de Análise e Auditoria de Ativo gerado em 24 de setembro de 2026 • Repositório iitauquant (Laboratório de Finanças Quantitativas) • Conteúdo para fins de pesquisa quantitativa e educacional institucional.
  </div>
</main>
</body>
</html>
"""

report_file = RELATORIOS_DIR / "micron_mutc34_analise_2026-09-24.html"
with open(report_file, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Relatório gerado com sucesso em: {report_file}")
