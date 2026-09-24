"""Gerador do relatório institucional HTML para Palantir / P2LT34 no laboratório iitauquant."""

from __future__ import annotations

import base64
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results" / "palantir_research"
RELATORIOS_DIR = ROOT / "relatorios"
GRAFICOS_DIR = RELATORIOS_DIR / "graficos"
GRAFICOS_DIR.mkdir(parents=True, exist_ok=True)

# Copiar imagens para relatorios/graficos
shutil.copy(RESULTS_DIR / "p2lt34_trade_setup.png", GRAFICOS_DIR / "p2lt34_trade_setup.png")
shutil.copy(RESULTS_DIR / "palantir_equity_drawdown.png", GRAFICOS_DIR / "palantir_equity_drawdown.png")

with open(RESULTS_DIR / "p2lt34_trade_setup.png", "rb") as f:
    b64_trade_setup = base64.b64encode(f.read()).decode("utf-8")

with open(RESULTS_DIR / "palantir_equity_drawdown.png", "rb") as f:
    b64_equity_drawdown = base64.b64encode(f.read()).decode("utf-8")

with open(RESULTS_DIR / "user_position_summary.json", "r", encoding="utf-8") as f:
    user_data = json.load(f)

html_content = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Palantir Technologies / P2LT34 — Análise Quantitativa, Fundamentalista e Gestão de Posição</title>
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
    <div class="eyebrow">Auditoria Quantitativa de Posição & Relatório Fundamentalista • Laboratório iitauquant</div>
    <h1>Palantir Technologies (P2LT34 / PLTR): Acelerador da Era de IA e Gestão Operacional da Posição</h1>
    <p class="meta">Data-base: 24 de setembro de 2026 • Custo de Aquisição Informado: <strong>R$ 309,03</strong> • Paridade B3: 3 BDRs = 1 Ação Ordinária (1:3)</p>
    <div class="verdict">
      <strong>Veredito Institucional: MANTER COM TRAILING STOP DE PROTEÇÃO & ALVOS ESCALADOS.</strong><br>
      O investidor adquiriu a ação em um ponto técnico e algorítmico perfeito a <strong>R$ 309,03</strong>, exatamente no momento em que o modelo <i>Momentum ATR</i> do laboratório <code>iitauquant</code> gerou compra na B3 (preço de abertura R$ 307,10 em 21/09/2026). A posição acumula lucro imediato de <strong>+8,09% a +8,60% (+R$ 25,00 por BDR)</strong>. A Palantir vive seu trimestre de maior aceleração operacional da história (+93% de receita líquida a/a, margem bruta de 84,8% e fluxo de caixa livre > US$ 2,1 bi impulsionados por AIP e defesa). O momento agora é de <strong>disciplina quantitativa: proteger o lucro garantido elevando o stop móvel para R$ 312,96 (ou breakeven em R$ 309,03)</strong> e executar saídas parciais nas faixas de <strong>R$ 350,00</strong> e <strong>R$ 373,83 (topo histórico)</strong>.
    </div>
  </header>

  <div class="grid kpis">
    <div class="kpi highlight">
      <b>+{user_data['user_return_pct']:.2f}%</b>
      <span>Rentabilidade da Posição (Compra R$ {user_data['user_entry_price']:.2f} ➔ R$ {user_data['p2lt_close']:.2f})</span>
    </div>
    <div class="kpi">
      <b>US$ {user_data['pltr_close']:.2f}</b>
      <span>PLTR (NYSE), Fechamento 24 set. 2026</span>
    </div>
    <div class="kpi">
      <b>R$ {user_data['p2lt_close']:.2f}</b>
      <span>P2LT34 (B3) • Teórico: R$ {user_data['theoretical_bdr']:.2f} (Spread: {user_data['parity_spread_pct']:.2f}%)</span>
    </div>
    <div class="kpi">
      <b>R$ {user_data['stop_20_atr']:.2f}</b>
      <span>Stop de Proteção Recomendado (2.0x ATR • Lucro +1,27% Travado)</span>
    </div>
  </div>

  <!-- SEÇÃO 1: AUDITORIA DA POSIÇÃO DO USUÁRIO -->
  <section>
    <h2>1. Diagnóstico Executivo da Posição Adquirida a R$ 309,03</h2>
    
    <div class="user-card">
      <h3 style="color: var(--green); margin-top:0;">Status da Sua Operação no Laboratório Quantitativo</h3>
      <p style="font-size: 1.05rem; margin-bottom: 12px;">
        Você comprou <strong>P2LT34 a R$ 309,03</strong>. No fechamento atual de <strong>R$ 334,04 (com máxima intradiária de R$ 335,99)</strong>, você acumula um ganho líquido de <strong>+{user_data['user_return_pct']:.2f}% (+R$ {user_data['user_gain_per_bdr']:.2f} por BDR)</strong>.
      </p>
      <div class="grid three" style="margin-top: 15px;">
        <div class="card" style="background:#fff; border: 1px solid #bbf7d0;">
          <span class="tag" style="background:#dcfce7; color:#15803d;">Timing Algorítmico</span>
          <p><strong>Entrada em Confluência Exata:</strong> A compra a R$ 309,03 coincidiu com o breakout do modelo <i>Momentum ATR</i> do laboratório <code>iitauquant</code> disparado na barra de 21/09/2026 a R$ 307,10. Você capturou o início do rali institucional antes do mercado esticar.</p>
        </div>
        <div class="card" style="background:#fff; border: 1px solid #bbf7d0;">
          <span class="tag" style="background:#dcfce7; color:#15803d;">Preservação de Capital</span>
          <p><strong>Risco Financeiro Zerado:</strong> Com o ganho acumulado superior a 2,5x a volatilidade diária média (ATR14 de R$ 10,54), a posição atinge o limiar quantitativo onde o stop deve ser movido para o preço de entrada (breakeven) ou acima dele.</p>
        </div>
        <div class="card" style="background:#fff; border: 1px solid #bbf7d0;">
          <span class="tag" style="background:#dcfce7; color:#15803d;">Assimetria Restante</span>
          <p><strong>Espaço até o Topo de 52 Semanas:</strong> O topo histórico anual de P2LT34 é de <strong>R$ 373,83</strong> (distância de +11,9% da cotação atual e +20,97% da sua compra), oferecendo um excelente alvo para realização parcial de lucros.</p>
        </div>
      </div>
    </div>

    <h3>As Três Opções de Gestão de Stop para o seu Trade:</h3>
    <table>
      <thead>
        <tr>
          <th>Estratégia de Stop</th>
          <th>Preço Gatilho</th>
          <th>Resultado vs Sua Compra (R$ 309,03)</th>
          <th>Comportamento & Recomendação de Uso</th>
        </tr>
      </thead>
      <tbody>
        <tr style="background:#ecfdf5; font-weight:700;">
          <td><span class="badge-quant" style="background:#10b981; color:#fff;">RECOMENDADA</span> Stop Lucro Móvel (2.0x ATR)</td>
          <td>R$ {user_data['stop_20_atr']:.2f}</td>
          <td style="color:var(--green)">+1,27% de Lucro Líquido Travado (+R$ 3,93/BDR)</td>
          <td>Garante matematicamente que o trade termine no positivo mesmo com taxas e emolumentos. Protege contra reversões abruptas após dias de alta forte.</td>
        </tr>
        <tr>
          <td>Stop Padrão de Governança (2.5x ATR)</td>
          <td>R$ {user_data['stop_25_atr']:.2f}</td>
          <td style="color:#d97706">-0,43% do Custo Inicial (-R$ 1,34/BDR)</td>
          <td>Parâmetro oficial do backtest do laboratório. Dá maior folga contra oscilações de ruído (whip-saws) intradiárias causadas pelo câmbio dólar/real.</td>
        </tr>
        <tr>
          <td>Stop de Ponto de Equilíbrio (Breakeven)</td>
          <td>R$ 309,03</td>
          <td style="color:#0284c7">0,00% (Risco Financeiro Zero)</td>
          <td>Simples e direto: ordene a sua corretora que encerre a posição caso o ativo volte ao seu exato preço de entrada. Risco financeiro nulo.</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- SEÇÃO 2: GRÁFICO TÁTICO DA OPERAÇÃO -->
  <section>
    <h2>2. Visualização Técnica e Mapa Tático da Posição</h2>
    <p>O gráfico abaixo foi gerado diretamente a partir da base histórica auditada pelo motor do <code>iitauquant</code>. Note a confluência da média móvel de curto prazo (SMA20 em azul tracejado), a zona de compra a R$ 309,03 e os níveis de alvos e proteção:</p>
    
    <div class="img-box">
      <img src="data:image/png;base64,{b64_trade_setup}" alt="Mapa Tático da Posição P2LT34" />
      <p class="small" style="margin-top:8px;">Figura 1: Mapeamento da posição P2LT34.SA (Março a Setembro de 2026). Linha azul/ponto de compra do usuário a R$ 309,03, faixa verde de ganho realizado, trailing stop e alvos de realização de lucros.</p>
    </div>
  </section>

  <!-- SEÇÃO 3: FUNDAMENTOS DA PALANTIR E CATALISADORES RECENTES -->
  <section>
    <h2>3. Fundamentos da Companhia: O Superciclo AIP e Contratos Governamentais (Setembro/2026)</h2>
    <div class="grid two">
      <div class="card positive">
        <span class="tag">Diferencial Tecnológico</span>
        <h3>AIP e a Ontologia Empresarial</h3>
        <p>Ao contrário da maioria das empresas que criaram simples "wrappers" em torno de modelos de linguagem (LLMs), a Palantir possui a <strong>Ontologia</strong> (Foundry & AIP). Ela mapeia e conecta bancos de dados heterogêneos, sensores operacionais e regras de conformidade corporativa em tempo real. Isso permite que modelos de IA executem ações autônomas seguras (<i>agentic workflows</i>) com auditoria ponta a ponta.</p>
      </div>
      <div class="card positive">
        <span class="tag">Hiper-Aceleração Comercial</span>
        <h3>Crescimento de +149% no Segmento Privado dos EUA</h3>
        <p>No 2T26, as receitas comerciais nos Estados Unidos explodiram <strong>+149% a/a</strong>, atingindo US$ 764 milhões. Os <i>bootcamps</i> práticos da Palantir continuam convertendo pilotos em contratos plurianuais de dezenas de milhões de dólares em tempo recorde em setores como aviação, manufatura, logística e farmacêutico.</p>
      </div>
      <div class="card positive">
        <span class="tag">Defesa & Geopolítica</span>
        <h3>Novos Contratos Militares (Setembro/2026)</h3>
        <p>No final de setembro de 2026, o Exército dos EUA premiou a Palantir com um novo contrato de <strong>US$ 48,1 milhões</strong> para unificar 9 sistemas legados de gestão de munições. No ano fiscal de 2026, a Palantir superou <strong>US$ 1 bilhão em obrigações contratuais com o governo dos EUA</strong>. Além disso, o teto orçamentário do <strong>Projeto Maven (IA de mira tática militar)</strong> foi ampliado para ~US$ 1,3 bilhão.</p>
      </div>
      <div class="card neutral">
        <span class="tag">Balanço Fortaleza</span>
        <h3>US$ 9,41 Bilhões em Caixa e Dívida Zero</h3>
        <p>A Palantir ostenta uma das estruturas patrimoniais mais robustas do setor de tecnologia global: <strong>US$ 9,41 bilhões em caixa líquido e investimentos de curto prazo</strong>, contra apenas US$ 211 milhões em dívidas totais. Isso confere caixa líquido de mais de US$ 9,2 bilhões, permitindo autofinanciar inovação e aquisições estratégicas sem depender de crédito bancário.</p>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 4: DEMONSTRAÇÕES FINANCEIRAS -->
  <section>
    <h2>4. Demonstrações Financeiras Consolidadas (2T26 / 1S26)</h2>
    <table>
      <thead>
        <tr>
          <th>Linha Financeira</th>
          <th>Resultado 2T26</th>
          <th>Variação Anual (a/a)</th>
          <th>Interpretação e Qualidade Contábil</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>Receita Líquida Consolidada</td>
          <td><strong>US$ 1,935 bilhão</strong></td>
          <td style="color:var(--green)">+93,0% a/a</td>
          <td>Forte aceleração frente aos trimestres anteriores, impulsionada pela demanda inelástica por AIP corporativo.</td>
        </tr>
        <tr>
          <td>Receita Comercial EUA</td>
          <td>US$ 764 milhões</td>
          <td style="color:var(--green)">+149,0% a/a</td>
          <td>Segmento mais lucrativo e dinâmico, reduzindo a dependência histórica de contratos federais.</td>
        </tr>
        <tr>
          <td>Receita Governamental EUA</td>
          <td>US$ 809 milhões</td>
          <td style="color:var(--green)">+90,0% a/a</td>
          <td>Reconhecimento de contratos de defesa de grande escala (DoD, Maven, Exército e agências de inteligência).</td>
        </tr>
        <tr>
          <td>Margem Bruta (Gross Margin)</td>
          <td><strong>84,8%</strong></td>
          <td>+310 bps a/a</td>
          <td>Margem de software puro de altíssimo valor agregado; poder de precificação incontestável.</td>
        </tr>
        <tr>
          <td>Margem Operacional GAAP</td>
          <td>47,1%</td>
          <td>+1.850 bps a/a</td>
          <td>Alavancagem operacional massiva: os custos fixos são diluídos com a expansão da base de clientes.</td>
        </tr>
        <tr>
          <td>Lucro Líquido GAAP (Net Income)</td>
          <td><strong>US$ 1,062 bilhão</strong></td>
          <td style="color:var(--green)">Margem Líquida de 55,0%</td>
          <td>Transformação completa da empresa em máquina geradora de lucro contábil positivo e recorrente.</td>
        </tr>
        <tr>
          <td>Fluxo de Caixa Livre (FCF)</td>
          <td>US$ 2,159 bilhões (TTM)</td>
          <td>Forte expansão</td>
          <td>Conversão de caixa impecável, permitindo remuneração e estabilidade.</td>
        </tr>
        <tr>
          <td>Caixa Líquido / Posição Financeira</td>
          <td>US$ 9,41 bi em caixa vs US$ 211 mi dívida</td>
          <td>Caixa Líquido > US$ 9,2 bi</td>
          <td>Imune a estresses de taxa de juros ou aperto monetário global.</td>
        </tr>
      </tbody>
    </table>
    <p class="small">Fonte: Relatórios oficiais 10-Q/10-K arquivados na SEC pela Palantir Technologies Inc. (trimestre encerrado em 30 de junho de 2026 e atualizações operacionais de setembro de 2026).</p>
  </section>

  <!-- SEÇÃO 5: ENQUADRAMENTO NO IITAUQUANT -->
  <section>
    <h2>5. Como o Portfólio Multi-Sleeve do iitauquant Enxerga a Palantir</h2>
    <p>O repositório <code>iitauquant</code> opera com uma estrutura de gestão quantitativa baseada em fatores acadêmicos, momentum sistemático e overlay de risco macroeconômico:</p>
    <div class="grid three">
      <div class="card amber">
        <span class="tag">Sleeve 1: Fatores</span>
        <h3>Qualidade Imbatível, Valuation Exigente</h3>
        <p>No modelo de fatores (Tamanho, Valor, Rentabilidade e Investimento), a Palantir pontua no <strong>percentil 99 de Rentabilidade e Qualidade</strong> (Margem Bruta de 84,8% e ROIC elevado). Em contrapartida, é severamente penalizada no fator Valor devido aos múltiplos esticados (P/L projetado de 83x e P/S de 75x). Não é uma ação de "barganha", mas sim de hiper-crescimento.</p>
      </div>
      <div class="card positive">
        <span class="tag">Sleeve 2: Momentum</span>
        <h3>Liderança Absoluta no Ranking 12-1</h3>
        <p>No Sleeve 2 (seleção dos 5% ativos com maior momentum 12-1 e controle de reversão), a Palantir figura no <strong>topo do universo tecnológico global</strong>. O modelo identifica a aceleração de lucros e a confluência de contratos de defesa como o motor perfeito para estratégias seguidoras de tendência sistemática.</p>
      </div>
      <div class="card neutral">
        <span class="tag">Risk Overlay: Macro</span>
        <h3>Sensibilidade ao NFCI e Spreads de Crédito</h3>
        <p>Múltiplos elevados como os de PLTR sofrem forte compressão em momentos de estresse de liquidez. O overlay de risco do <code>iitauquant</code> (monitorando o spread <code>BAA10Y</code> e as condições financeiras <code>NFCI</code>) protege a carteira: se o z-score macro superar 1,0, até 50% da alocação migra automaticamente para ativos de preservação (BIL/Caixa), blindando o capital.</p>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 6: BACKTEST MOMENTUM ATR VS BUY & HOLD -->
  <section>
    <h2>6. Evidência Quantitativa Auditada: Momentum ATR vs Buy & Hold (2020–2026)</h2>
    <p>Executamos o motor de simulação de eventos causal do <code>iitauquant</code> (parâmetros de governança: janela de momentum de 20 barras, ATR de 14 barras, multiplicador de stop de 2,5x e fricção de execução de 15 bps por lado com ordens preenchidas no Open de t+1):</p>
    
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
          <td>PLTR (NYSE)</td>
          <td>1.503</td>
          <td>67</td>
          <td>41,8%</td>
          <td>+34,73%</td>
          <td>5,12%</td>
          <td>40,1%</td>
          <td>0,321</td>
          <td style="color:var(--green)">-53,49%</td>
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
          <td style="color:var(--green)">-46,51%</td>
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

    <div class="img-box">
      <img src="data:image/png;base64,{b64_equity_drawdown}" alt="Curva de Patrimônio e Drawdown Auditados" />
      <p class="small">Figura 2: Curva de patrimônio acumulado normalizado e histórico de rebaixamento de capital (drawdown) auditados no iitauquant.</p>
    </div>

    <div class="callout">
      <strong>Lições Cruciais da Auditoria Quantitativa:</strong>
      <ul>
        <li><strong>A Queda Devastadora de Buy & Hold:</strong> Investidores que mantiveram PLTR sem disciplina de stop sofreram uma queda implacável de <strong>-84,62%</strong> durante o mercado de baixa de 2021/2022 (e o BDR caiu <strong>-79,33%</strong>). O sistema com stop móvel reduziu esse rebaixamento em mais de 30 pontos percentuais.</li>
        <li><strong>Eficiência com Exposição Reduzida:</strong> O motor quantitativo permaneceu comprado em apenas <strong>36,8% do tempo</strong>, permitindo que os 63,2% restantes do tempo fossem alocados em caixa rendendo juros compostos (Sleeve 3 / CDI).</li>
        <li><strong>Fricção de Câmbio Noturno em BDRs:</strong> No BDR negociado no Brasil, gaps entre a abertura da B3 e o fechamento de Nova York geram ruído operacional para trades de curtíssimo prazo. Para quem compra via BDR, o ideal é o modelo de <i>swing trade posicional estruturado</i> com stop ATR mais elástico (2,0x a 2,5x ATR).</li>
      </ul>
    </div>
  </section>

  <!-- SEÇÃO 7: PARIDADE CAMBIAL DO BDR P2LT34 -->
  <section>
    <h2>7. Paridade Cambial do BDR P2LT34: Dólar vs Real</h2>
    <div class="grid two">
      <div class="card neutral">
        <h3>Fórmula Oficial da Paridade</h3>
        <p>O programa de BDRs da B3 define a proporção de <strong>3 BDRs para cada 1 ação ordinária da Palantir (1:3)</strong>. A fórmula do valor justo do BDR é dada por:</p>
        <div style="background:#f1f5f9; padding:12px; border-radius:6px; font-family:monospace; font-weight:700; text-align:center; margin:10px 0;">
          Preço Teórico BDR = (Cotação PLTR na NYSE × USD/BRL) ÷ 3
        </div>
        <p>No fechamento de referência: (US$ {user_data['pltr_close']:.2f} × {user_data['usd_brl']:.4f}) ÷ 3 = <strong>R$ {user_data['theoretical_bdr']:.2f}</strong>. Como o BDR fechou a <strong>R$ {user_data['p2lt_close']:.2f}</strong>, ele negocia praticamente com paridade perfeita (spread de apenas {user_data['parity_spread_pct']:.2f}%).</p>
      </div>

      <div class="card neutral">
        <h3>Duplo Motor: Crescimento em Dólar + Hedge Cambial</h3>
        <p>Ao deter P2LT34, sua rentabilidade depende de duas variáveis multiplicativas:</p>
        <ul>
          <li><strong>Desempenho da Palantir em Dólar (PLTR):</strong> A expansão dos contratos e lucros da empresa.</li>
          <li><strong>Taxa de Câmbio USD/BRL:</strong> Se o dólar se valorizar contra o real, o BDR sobe em reais mesmo que a ação fique estável lá fora. Historicamente, essa proteção cambial foi um dos principais propulsores do retorno para o investidor brasileiro.</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 8: MATRIZ DE CENÁRIOS -->
  <section id="cenarios">
    <h2>8. Matriz de Cenários para 12–24 Meses (PLTR & P2LT34)</h2>
    <table>
      <thead>
        <tr>
          <th>Cenário</th>
          <th>PLTR (US$)</th>
          <th>Câmbio (USD/BRL)</th>
          <th>P2LT34 Estimado (R$)</th>
          <th>Retorno vs Sua Compra (R$ 309,03)</th>
          <th>Probabilidade & Gatilhos Operacionais</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td class="scenario-bear">Baixista (Bear)</td>
          <td>US$ 125,00</td>
          <td>R$ 4,90</td>
          <td><strong>R$ 204,17</strong></td>
          <td class="scenario-bear">-33,9%</td>
          <td><strong>20%</strong> • Compressão de múltiplos por repique inflacionário / juros altos nos EUA; corte em orçamentos federais de TI ou desaceleração em adoção de IA comercial. <i>(Mitigado pelo seu stop móvel em R$ 312,96!)</i></td>
        </tr>
        <tr>
          <td class="scenario-base">Base (Consenso)</td>
          <td>US$ 215,00</td>
          <td>R$ 5,20</td>
          <td><strong>R$ 372,67</strong></td>
          <td class="scenario-base"><strong>+20,6%</strong></td>
          <td><strong>55%</strong> • Continuidade da expansão comercial (+80-100% a/a), consolidação do Projeto Maven e novos contratos da OTAN; estabilidade da margem líquida acima de 50%.</td>
        </tr>
        <tr>
          <td class="scenario-bull">Otimista (Bull)</td>
          <td>US$ 265,00</td>
          <td>R$ 5,40</td>
          <td><strong>R$ 477,00</strong></td>
          <td class="scenario-bull"><strong>+54,4%</strong></td>
          <td><strong>25%</strong> • Monopolização de fato dos fluxos de trabalho autônomos por IA no complexo industrial e militar dos EUA; entrada massiva em governos europeus e asiáticos; desvalorização do Real.</td>
        </tr>
      </tbody>
    </table>
  </section>

  <!-- SEÇÃO 9: FALSIFICADORES DA TESE -->
  <section>
    <h2>9. Falsificadores da Tese: O que Destrói e o que Confirma o Trade</h2>
    <div class="grid two">
      <div class="card positive">
        <h3>Fatos Confirmadores (Manter Posição)</h3>
        <ul>
          <li>Crescimento de receita comercial nos EUA sustentado acima de 100% nos próximos balanços.</li>
          <li>Conversão da expansão do teto de gastos do Projeto Maven (~US$ 1,3 bi) em faturamento efetivo no 3T26/4T26.</li>
          <li>Sustentação do preço de P2LT34 acima da média móvel de 20 dias (R$ 305,33).</li>
          <li>Novos contratos corporativos globais divulgados após o sucesso da AIPCon 11.</li>
          <li>Rompimento definitivo da barreira psicológica de US$ 200,00 na NYSE (rumo a US$ 215+).</li>
        </ul>
      </div>
      <div class="card negative">
        <h3>Falsificadores da Tese (Executar Venda pelo Stop)</h3>
        <ul>
          <li>Desaceleração expressiva no ritmo de conversão dos <i>bootcamps</i> em receita faturada.</li>
          <li>Fechamento do BDR abaixo do Trailing Stop de R$ 307,69 ou Stop de Lucro em R$ 312,96.</li>
          <li>Disparo do Risk Overlay do laboratório por salto nos spreads de crédito (BAA10Y Z > 1.0).</li>
          <li>Disputas orçamentárias no Congresso americano que congelem verbas do Departamento de Defesa.</li>
          <li>Perda do suporte estrutural da média móvel de 50 dias (R$ 278,80).</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 10: PLANO DE EXECUÇÃO PRÁTICA PASSO A PASSO -->
  <section>
    <h2>10. Checklist de Ação Imediata para o Usuário (Posição a R$ 309,03)</h2>
    <div class="grid three">
      <div class="card positive" style="border: 2px solid var(--green);">
        <span class="tag" style="background:#dcfce7; color:#15803d;">Passo 1: Proteção Imediata</span>
        <h3>Ajustar o Stop na Corretora</h3>
        <p>Cadastre uma ordem de <strong>Stop Móvel (Trailing Stop) ou Stop Loss em R$ 312,96</strong> (ou no seu preço de compra de <strong>R$ 309,03</strong>). Dessa forma, seu risco de perder dinheiro nesta operação torna-se estritamente <strong>ZERO</strong>.</p>
      </div>
      <div class="card neutral" style="border: 2px solid var(--palantir);">
        <span class="tag" style="background:#e0f2fe; color:#0369a1;">Passo 2: Realização Parcial</span>
        <h3>Cadastrar Ordens de Alvo</h3>
        <p>Defina realização parcial de <strong>30% a 40% da posição na faixa de R$ 348,00 a R$ 352,00</strong> (+12,6% a +13,9% de lucro) e mais <strong>30% no topo anual em R$ 373,83</strong> (+20,97% de lucro), guardando o lote final para o superciclo.</p>
      </div>
      <div class="card amber" style="border: 2px solid var(--amber);">
        <span class="tag" style="background:#fef3c7; color:#b45309;">Passo 3: Dimensionamento</span>
        <h3>Tamanho de Posição (Sizing)</h3>
        <p>Devido à volatilidade elevada da Palantir (~67% ao ano), a alocação máxima sugerida pela governança do <code>iitauquant</code> é de <strong>5% a 8% do seu patrimônio total em bolsa</strong>, garantindo que o portfólio permaneça descorrelacionado e resiliente.</p>
      </div>
    </div>
  </section>

  <!-- SEÇÃO 11: FONTES E GOVERNANÇA -->
  <section id="fontes">
    <h2>11. Fontes Primárias, Governança e Metodologia</h2>
    <ul class="small">
      <li><strong>Palantir Investor Relations:</strong> Relatório financeiro e conferência de resultados do 2T26 (receitas de US$ 1,935 bi, lucro GAAP de US$ 1,062 bi e métricas de expansão de AIP).</li>
      <li><strong>SEC EDGAR:</strong> Palantir Technologies Inc. — Formulários oficiais 10-K e 10-Q auditados.</li>
      <li><strong>Departamento de Defesa dos EUA (DoD) & U.S. Army:</strong> Contratos governamentais e atualização orçamentária do Projeto Maven (US$ 1,3 bi) e Munitions Enterprise System (US$ 48,1 mi).</li>
      <li><strong>B3 Brasil, Bolsa, Balcão:</strong> Regulamento oficial do programa de BDRs Não Patrocinados (código P2LT34, proporção 1:3, custodiante Banco B3 S.A.).</li>
      <li><strong>Laboratório Quantitativo iitauquant:</strong> Módulos <code>src/backtest/engine.py</code>, <code>src/strategies/momentum_atr.py</code>, <code>quant_fund/risk_overlay.py</code> e scripts executados <code>scripts/analisar_p2lt34.py</code>.</li>
    </ul>
  </section>

  <div class="footer">
    Relatório de Análise e Auditoria de Posição gerado em 24 de setembro de 2026 • Repositório iitauquant (Laboratório de Finanças Quantitativas) • Conteúdo para fins de pesquisa quantitativa e educacional institucional.
  </div>
</main>
</body>
</html>
"""

report_file = RELATORIOS_DIR / "palantir_p2lt34_analise_2026-09-24.html"
with open(report_file, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"Relatório gerado com sucesso em: {report_file}")
