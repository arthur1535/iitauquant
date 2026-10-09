"""Standalone, offline research reports for the US swing research pipeline."""

from __future__ import annotations

from datetime import datetime
from html import escape
import math
from pathlib import Path
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo


_STATUS = {
    "candidato": "Sinal técnico presente",
    "observar": "Aguardar sinal",
    "bloqueado": "Não avançar",
}


def _e(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _num(value: object) -> float | None:
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def _decimal(value: object, digits: int = 2, signed: bool = False) -> str:
    number = _num(value)
    if number is None:
        return "—"
    text = f"{number:+,.{digits}f}" if signed else f"{number:,.{digits}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def _pct(value: object, signed: bool = True, digits: int = 1) -> str:
    number = _num(value)
    return "—" if number is None else _decimal(number * 100, digits, signed) + "%"


def _pp(value: object) -> str:
    number = _num(value)
    return "—" if number is None else _decimal(number * 100, 1, True) + " p.p."


def _local_time(value: object) -> str:
    try:
        instant = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if instant.tzinfo is None:
            return str(value)
        return instant.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M BRT")
    except (ValueError, TypeError):
        return str(value or "não informado")


def _usd(value: object) -> str:
    return "—" if _num(value) is None else "US$ " + _decimal(value)


def _liquidity(value: object) -> str:
    number = _num(value)
    if number is None:
        return "—"
    if abs(number) >= 1_000_000_000:
        return "US$ " + _decimal(number / 1_000_000_000, 1) + " bi"
    return "US$ " + _decimal(number / 1_000_000, 1) + " mi"


def _tone(value: object) -> str:
    number = _num(value)
    return "muted" if number is None else "positive" if number > 0 else "negative" if number < 0 else ""


def _sort_value(value: object) -> str:
    number = _num(value)
    return "" if number is None else str(number)


def _kind(row: dict) -> str:
    value = str(row.get("kind", "")).lower()
    return "ETF" if value in {"etf", "fund", "exchange-traded fund"} else "Ação"


def _url(source: dict | None, ticker: str) -> str:
    value = str((source or {}).get("url", ""))
    if urlparse(value).scheme in {"http", "https"} and urlparse(value).netloc:
        return value
    return "https://finance.yahoo.com/quote/" + quote(ticker, safe="") + "/history/"


def _source_note(row: dict, source: dict | None) -> str:
    ticker = str(row.get("ticker", ""))
    provider = str((source or {}).get("source") or "Yahoo Finance")
    return (
        f'<a href="{_e(_url(source, ticker))}" target="_blank" rel="noopener noreferrer">'
        f"{_e(provider)} · {_e(ticker)}</a>"
        f' · fechamento de <time>{_e(row.get("as_of", "não informado"))}</time>'
    )


def _edge_issues(row: dict, minimum: int) -> list[str]:
    issues = []
    trades = _num(row.get("oos_trades"))
    ret = _num(row.get("oos_return"))
    sharpe = _num(row.get("oos_sharpe"))
    stress = _num(row.get("cost_stress_return"))
    if trades is None or trades < minimum:
        issues.append(f"amostra OOS inferior a {minimum} operações")
    if ret is None or ret <= 0:
        issues.append("retorno OOS ausente ou não positivo")
    if sharpe is None or sharpe <= 0:
        issues.append("Sharpe OOS ausente ou não positivo")
    if stress is None or stress <= 0:
        issues.append("retorno sob custos maiores ausente ou não positivo")
    return issues


def _edge_label(row: dict, minimum: int) -> str:
    return "Sem vantagem demonstrada" if _edge_issues(row, minimum) else "OOS favorável; evidência exploratória"


def _reasons(row: dict) -> list[str]:
    reasons = row.get("reasons") or []
    return [str(value) for value in reasons if value] if isinstance(reasons, list) else [str(reasons)]


def _first_rejection(row: dict, minimum: int) -> str:
    reasons = _reasons(row)
    if reasons:
        return reasons[0]
    issues = _edge_issues(row, minimum)
    if issues:
        return issues[0].capitalize() + "."
    return "Resultados corporativos e eventos ainda precisam de confirmação."


def _card(row: dict, position: int, minimum: int, source: dict | None, config: dict) -> str:
    ticker = _e(row.get("ticker"))
    status = str(row.get("status", "observar"))
    issues = _edge_issues(row, minimum)
    why = (
        f"Momentum de 20 pregões em {_pct(row.get('return_20d'))}; "
        f"força relativa ao SPY em {_pp(row.get('relative_20d'))}. "
        "Isso prioriza pesquisa de continuidade de preço, sem estimar valor justo."
    )
    if _kind(row) == "ETF":
        missing = "Composição atual, concentração, sobreposição, spread e eventos do índice."
        next_step = "Conferir fatos do emissor, principais posições e sobreposição antes de simular entrada."
    else:
        missing = "Próximos resultados, comunicados de RI, notícias materiais e spread de negociação."
        next_step = "Conferir calendário no RI e notícias; atualizar o sinal após o próximo fechamento."
    investable = (
        "Manter os filtros quantitativos, validar eventos e custos de execução e confirmar "
        "o sinal com dados novos. O resultado segue como candidato de pesquisa."
    )
    invalidates = (
        "Perda do sinal de tendência, falha nos filtros de risco/liquidez ou evento que "
        "altere a tese. Gap pode atravessar a referência de saída."
    )
    evidence = "; ".join(issues).capitalize() + "." if issues else (
        "Resultados positivos no recorte OOS não estabelecem significância estatística nem repetição futura."
    )
    if (_num(row.get("oos_return")) or 0) > 1:
        evidence += " Retorno histórico excepcional: não extrapolar como expectativa; a seleção entre ativos não foi corrigida por múltiplas comparações."
    return f"""
<article class="idea-card">
  <div class="card-top"><span class="eyebrow">Prioridade {position:02d} · {_e(_kind(row))}</span>
    <span class="badge {_e(status)}">{_e(_STATUS.get(status, status))}</span></div>
  <h3>{ticker}<span>{_e(row.get('name') or ticker)}</span></h3>
  <p class="source-note">{_source_note(row, source)}</p>
  <div class="card-metrics">
    <div><span>Fechamento de referência</span><strong>{_usd(row.get('last_close'))}</strong></div>
    <div><span>Score de ordenação</span><strong>{_decimal(row.get('score'), 1)}</strong></div>
    <div><span>ATR / preço</span><strong>{_pct(row.get('atr_pct'), False)}</strong></div>
    <div><span>OOS líquido · {_decimal(row.get('oos_trades'), 0)} operações</span>
      <strong class="{_tone(row.get('oos_return'))}">{_pct(row.get('oos_return'))}</strong></div>
  </div>
  <p class="evidence-line {'limited' if issues else ''}"><strong>{_e(_edge_label(row, minimum))}.</strong> {_e(evidence)}</p>
  <dl class="idea-thesis">
    <div><dt>Por que agora</dt><dd>{_e(why)}</dd></div>
    <div><dt>Primeiro motivo de rejeição</dt><dd>{_e(_first_rejection(row, minimum))}</dd></div>
    <div><dt>O que tornaria investível</dt><dd>{_e(investable)}</dd></div>
    <div><dt>O que invalida</dt><dd>{_e(invalidates)}</dd></div>
    <div><dt>Evidência faltante</dt><dd>{_e(missing)} Desconto fundamental e expectativas do mercado não medidos.</dd></div>
  </dl>
  <div class="risk-reference"><span>Referência técnica de saída · {_decimal(config.get('stop_atr', 2), 1)} ATR</span>
    <strong>{_usd(row.get('stop_reference'))}</strong>
    <small>Referência de pesquisa na escala atual; não é ordem nem cotação executável. Peso teórico pelo orçamento de risco: {_pct(row.get('weight_at_risk_budget'), False)} do capital, antes de combinar posições.</small></div>
  <p class="next-step"><strong>Próxima etapa</strong> {_e(next_step)}</p>
</article>"""


def _ranking_row(row: dict, position: int, minimum: int, source: dict | None) -> str:
    status = str(row.get("status", "observar"))
    ticker = str(row.get("ticker", ""))
    return f"""
<tr data-ticker="{_e(ticker)}" data-search="{_e(' '.join(str(row.get(k) or '') for k in ('ticker', 'name', 'sector'))).lower()}"
 data-kind="{_e(_kind(row))}" data-status="{_e(status)}" data-score="{_sort_value(row.get('score'))}"
 data-return20="{_sort_value(row.get('return_20d'))}" data-oos="{_sort_value(row.get('oos_return'))}"
 data-vol="{_sort_value(row.get('volatility_20d'))}" data-adv="{_sort_value(row.get('adv_usd'))}">
 <th scope="row"><span class="rank">{position:02d}</span><a href="{_e(_url(source, ticker))}" target="_blank" rel="noopener noreferrer">{_e(ticker)}</a>
 <small>{_e(row.get('name') or ticker)} · {_e(_kind(row))}<br>{_e(row.get('sector') or 'Setor não informado')}</small></th>
 <td><span class="badge {_e(status)}">{_e(_STATUS.get(status, status))}</span><small>{_e(_first_rejection(row, minimum))}</small></td>
 <td>{_decimal(row.get('score'), 1)}</td>
 <td>{_usd(row.get('last_close'))}<small>{_e(row.get('as_of'))}</small></td>
 <td class="{_tone(row.get('return_20d'))}">{_pct(row.get('return_20d'))}</td>
 <td class="{_tone(row.get('relative_20d'))}">{_pp(row.get('relative_20d'))}</td>
 <td>{_pct(row.get('volatility_20d'), False)}</td>
 <td>{_pct(row.get('atr_pct'), False)}</td>
 <td>{_liquidity(row.get('adv_usd'))}</td>
 <td class="{_tone(row.get('oos_return'))}">{_pct(row.get('oos_return'))}<small>{_decimal(row.get('oos_trades'), 0)} operações</small></td>
 <td class="evidence-cell">{_e(_edge_label(row, minimum))}</td>
</tr>"""


def _oos_row(row: dict) -> str:
    return (
        f"<tr><th scope='row'>{_e(row.get('ticker'))}<small>{_e(row.get('oos_start'))} → {_e(row.get('oos_end'))}</small></th>"
        f"<td class='{_tone(row.get('oos_return'))}'>{_pct(row.get('oos_return'))}</td>"
        f"<td>{_decimal(row.get('oos_sharpe'))}</td><td>{_pct(row.get('oos_drawdown'))}</td>"
        f"<td>{_decimal(row.get('oos_trades'), 0)}</td><td>{_pct(row.get('oos_win_rate'), False)}</td>"
        f"<td>{_pct(row.get('oos_buy_hold_return'))}</td><td>{_pct(row.get('oos_spy_return'))}</td>"
        f"<td class='{_tone(row.get('cost_stress_return'))}'>{_pct(row.get('cost_stress_return'))}</td></tr>"
    )


def _correlations(ranking: list[dict], matrix: dict) -> str:
    names = [str(row.get("ticker")) for row in ranking if row.get("status") != "bloqueado"][:5]
    if len(names) < 2 or not matrix:
        return '<p class="muted">Amostra insuficiente para comparar a correlação entre prioridades.</p>'
    head = "".join(f"<th scope='col'>{_e(name)}</th>" for name in names)
    rows = []
    for name in names:
        cells = []
        for other in names:
            number = _num((matrix.get(name) or {}).get(other))
            strength = min(1.0, abs(number or 0))
            color = f"rgba(21, 106, 94, {0.05 + strength * 0.21:.3f})" if (number or 0) >= 0 else f"rgba(167, 79, 51, {0.05 + strength * 0.21:.3f})"
            cells.append(f'<td style="background:{color}">{_decimal(number)}</td>')
        rows.append(f"<tr><th scope='row'>{_e(name)}</th>{''.join(cells)}</tr>")
    return f"<div class='table-scroll'><table class='correlation'><caption>Retornos diários · últimos 60 pregões · correlação histórica</caption><thead><tr><th scope='col'>Ativo</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>"


_CSS = """
:root{--ink:#132c3b;--muted:#5a6b73;--paper:#f5f4ef;--white:#fff;--line:#d9dfda;--green:#156a5e;--amber:#986523;--red:#a14836;--serif:Georgia,'Times New Roman',serif}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.55 system-ui,-apple-system,'Segoe UI',sans-serif}a{color:var(--green);text-underline-offset:3px}button,input,select{font:inherit}button,a,input,select{touch-action:manipulation}button:focus-visible,a:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #d89639;outline-offset:3px}.wrap{max-width:1440px;margin:auto;padding:0 44px}.masthead{display:flex;align-items:center;justify-content:space-between;padding:24px 0;border-bottom:1px solid var(--line);gap:20px}.brand{font-weight:800;letter-spacing:-.7px;font-size:22px;color:var(--ink);text-decoration:none}.brand span{color:var(--green)}.masthead nav{display:flex;align-items:center;gap:22px;font-size:13px}.masthead nav a{color:var(--muted);text-decoration:none}.print{border:1px solid var(--line);border-radius:5px;background:transparent;padding:8px 13px;cursor:pointer;color:var(--ink)}.hero{padding:54px 0 30px;display:grid;grid-template-columns:1fr 290px;gap:50px;align-items:end}.eyebrow{text-transform:uppercase;letter-spacing:1.6px;font-size:11px;font-weight:700;color:var(--green)}h1{font:clamp(34px,3.5vw,50px)/1.12 var(--serif);letter-spacing:-1.1px;font-weight:400;margin:12px 0 18px;max-width:900px}h2{font:30px/1.2 var(--serif);font-weight:400;letter-spacing:-.4px;margin:0}h3{margin:15px 0 4px;font-size:28px;letter-spacing:-.6px}p{margin:0 0 16px}.hero .lead{font-size:17px;max-width:840px;color:var(--muted)}.hero-meta{padding:20px 0 20px 25px;border-left:2px solid var(--green)}.hero-meta p{margin:0 0 13px}.hero-meta small,.hero-meta span{display:block;color:var(--muted);font-size:12px}.hero-meta strong{font-size:16px;font-weight:600}.hero-note{font-size:12px;color:var(--muted);margin-bottom:25px}.funnel{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid var(--line);border-radius:7px;background:var(--white);overflow:hidden}.funnel-item{padding:22px 25px;position:relative}.funnel-item+.funnel-item{border-left:1px solid var(--line)}.funnel-item strong{display:block;font-size:34px;font-weight:500;line-height:1.2;font-variant-numeric:tabular-nums}.funnel-item span{display:block;font-size:13px;margin-top:8px}.funnel-item small{display:block;font-size:11px;color:var(--muted);margin-top:4px}.funnel-item.advance{background:#e9f2ec}.section{margin-top:46px;scroll-margin-top:22px}.section-head{display:flex;justify-content:space-between;align-items:end;gap:30px;margin-bottom:20px}.section-head p{color:var(--muted);font-size:13px;max-width:620px;margin:0}.section-kicker{display:block;color:var(--green);font-size:11px;letter-spacing:1.3px;text-transform:uppercase;font-weight:700;margin-bottom:8px}.ideas{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.idea-card{background:var(--white);border:1px solid var(--line);border-top:3px solid var(--green);padding:22px;border-radius:6px;min-width:0}.card-top{display:flex;gap:10px;flex-wrap:wrap;align-items:center;justify-content:space-between}.card-top .eyebrow{font-size:10px;letter-spacing:1px}h3 span{display:block;font-size:13px;font-weight:400;color:var(--muted);letter-spacing:0;margin-top:3px}.source-note{font-size:11px;color:var(--muted);margin-top:13px}.source-note a{color:var(--muted)}.badge{display:inline-block;border:1px solid #bfd8cc;border-radius:3px;font-size:10px;font-weight:650;line-height:1.4;padding:4px 7px;background:#eaf4ed;color:var(--green);white-space:normal}.badge.observar{background:#fbf3e7;border-color:#ead8b5;color:var(--amber)}.badge.bloqueado{background:#f7ece8;border-color:#e9c9bf;color:var(--red)}.card-metrics{display:grid;grid-template-columns:1fr 1fr;gap:15px 12px;padding:18px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);margin:18px 0}.card-metrics span{font-size:10px;color:var(--muted);display:block}.card-metrics strong{font-size:20px;font-weight:600;font-variant-numeric:tabular-nums;display:block;margin-top:4px}.evidence-line{font-size:11px;line-height:1.6;padding:11px 12px;background:#eff4f1;border-radius:4px}.evidence-line strong{font-weight:650}.evidence-line.limited{background:#faf3e8;color:#79501c}.idea-thesis{margin:18px 0}.idea-thesis div{margin:0 0 14px}.idea-thesis dt{font-size:11px;font-weight:750;color:var(--ink);margin-bottom:3px}.idea-thesis dd{font-size:12px;color:var(--muted);margin:0}.risk-reference{padding:13px 0;border-top:1px solid var(--line)}.risk-reference span{font-size:10px;color:var(--muted);display:block}.risk-reference strong{font-size:22px;font-weight:500}.risk-reference small{font-size:10px;color:var(--muted);display:block;line-height:1.5;margin-top:4px}.next-step{font-size:11px;margin:0;background:#f2f5f1;padding:12px;border-radius:3px;color:var(--muted)}.next-step strong{display:block;color:var(--green);margin-bottom:3px}.empty-state{padding:25px;background:#fff;border:1px solid var(--line);border-radius:6px;color:var(--muted)}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:18px 0 12px}.controls label{display:flex;flex-direction:column;gap:5px;font-size:11px;color:var(--muted)}.controls input,.controls select{padding:10px 12px;background:#fff;border:1px solid #cbd5ce;border-radius:4px;color:var(--ink);font-size:13px;min-height:41px}.controls input{min-width:230px}.result-count{margin:0 0 13px;color:var(--muted);font-size:12px}.table-scroll{overflow:auto;background:#fff;border:1px solid var(--line);border-radius:6px}table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.45}caption{text-align:left;padding:14px 18px;font-size:12px;color:var(--muted);border-bottom:1px solid var(--line)}th,td{text-align:right;vertical-align:top;padding:14px 13px;border-bottom:1px solid #e7eae5;white-space:nowrap;font-variant-numeric:tabular-nums}thead th{font-size:10px;font-weight:700;background:#eff2ed;color:var(--muted);padding:13px;position:sticky;top:0;z-index:1}thead th button{background:none;border:0;padding:0;color:inherit;font-size:inherit;font-weight:inherit;cursor:pointer}th:first-child,td:first-child{text-align:left}tbody th{font-size:13px;font-weight:700;min-width:190px}tbody th a{text-decoration:none;color:var(--ink)}tbody small{display:block;font-size:10px;line-height:1.4;font-weight:400;color:var(--muted);white-space:normal;max-width:195px;margin-top:4px}.rank{color:#87938e;font-size:10px;margin-right:10px}#ranking td:nth-child(2){min-width:200px;text-align:left}#ranking td:nth-child(2) small{max-width:210px}.evidence-cell{text-align:left;max-width:160px;min-width:140px;white-space:normal;font-size:10px;color:var(--muted)}tbody tr:last-child>*{border-bottom:0}tbody tr:hover{background:#fafbf8}.positive{color:var(--green)}.negative{color:var(--red)}.muted{color:var(--muted)}.table-footnote{font-size:11px;line-height:1.6;color:var(--muted);margin:12px 0}.two-column{display:grid;grid-template-columns:1fr 1fr;gap:24px}.panel{border:1px solid var(--line);border-radius:6px;background:#fff;padding:25px;min-width:0}.panel h2{font-size:26px;margin-bottom:14px}.panel p,.panel li{font-size:13px;color:var(--muted)}.panel ul,.method-list{padding-left:19px;margin:0}.panel li{margin-bottom:11px}.panel li:last-child{margin-bottom:0}.correlation{font-size:12px}.correlation caption{font-size:11px}.correlation th,.correlation td{padding:12px;text-align:center;min-width:55px}.correlation th:first-child{text-align:left}.warning-list{margin:0;padding:16px 20px 16px 35px;background:#fff5e5;border-left:3px solid #b68139;border-radius:3px}.warning-list li{color:#785624;font-size:12px;margin:5px 0}.details-grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;margin-top:24px}.details-grid h3{font:24px var(--serif);margin:0 0 13px}.details-grid li{font-size:12px;color:var(--muted);margin-bottom:10px}.method-list{margin-top:14px}.rejected-list{font-size:12px;list-style:none;padding:0;margin:0}.rejected-list li{border-top:1px solid var(--line);padding:12px 0;display:flex;gap:15px}.rejected-list strong{min-width:65px;color:var(--ink)}details{margin-top:20px;border:1px solid var(--line);border-radius:5px;background:#fff;padding:15px 18px}summary{cursor:pointer;font-size:13px;font-weight:600}details p{margin:12px 0 0;color:var(--muted);font-size:12px}.sources-table td:nth-child(2),.sources-table td:last-child{text-align:left}.sources-table th:first-child{min-width:90px}.hash{font:10px/1.5 ui-monospace,monospace;white-space:normal;word-break:break-all;max-width:250px}.source-rows{margin-top:20px}.footer{border-top:1px solid var(--line);margin:45px 0 0;padding:24px 0 30px;display:flex;justify-content:space-between;gap:30px;color:var(--muted);font-size:11px}.footer p{max-width:820px;margin:0}.noscript{padding:12px;background:#fff3dc;color:#79501c;font-size:12px}.screen-reader{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
.funnel{grid-template-columns:repeat(5,1fr)}
@media(min-width:1500px){.wrap{max-width:1500px}.idea-card{padding:25px}}
@media(max-width:1100px){.wrap{padding:0 25px}.hero{gap:30px;grid-template-columns:1fr 240px}.ideas{grid-template-columns:repeat(2,minmax(0,1fr))}.idea-card:last-child:nth-child(odd){grid-column:1/-1}.idea-card:last-child:nth-child(odd) .idea-thesis{display:grid;grid-template-columns:1fr 1fr;column-gap:25px}.masthead nav{gap:14px}.section-head{align-items:start}}
@media(max-width:740px){.wrap{padding:0 18px}.masthead{padding:18px 0}.masthead nav a{display:none}.hero{grid-template-columns:1fr;padding:34px 0 23px;gap:17px}h1{font-size:35px}.hero-meta{padding:14px 0 0;border-left:0;border-top:1px solid var(--line);display:flex;flex-wrap:wrap;gap:10px 28px}.hero-meta p{margin:0}.hero-meta small{display:none}.hero-meta strong{font-size:13px}.hero .lead{font-size:15px}.funnel{grid-template-columns:1fr 1fr}.funnel-item{padding:18px}.funnel-item:nth-child(3){border-left:0}.funnel-item:nth-child(n+3){border-top:1px solid var(--line)}.funnel-item strong{font-size:28px}.section{margin-top:34px}.section-head{display:block}.section-head p{margin-top:10px}h2{font-size:28px}.ideas,.two-column,.details-grid{grid-template-columns:1fr}.idea-card:last-child:nth-child(odd){grid-column:auto}.idea-card:last-child:nth-child(odd) .idea-thesis{display:block}.controls label:first-child{width:100%}.controls input{min-width:0;width:100%}.controls label{flex-grow:1}.controls select{max-width:100%;width:100%}.footer{display:block}.footer p{margin-bottom:10px}.panel{padding:20px}}
@media print{@page{size:A4 landscape;margin:12mm}body{background:#fff;font-size:10px;-webkit-print-color-adjust:exact;print-color-adjust:exact}.wrap{max-width:none;padding:0}.masthead{padding:0 0 10px}.masthead nav,.controls,.result-count,.print,.noscript{display:none!important}.hero{padding:20px 0;grid-template-columns:1fr 220px;gap:25px}h1{font-size:30px}.hero .lead{font-size:12px}.hero-note{font-size:9px}.funnel-item{padding:12px 16px}.funnel-item strong{font-size:25px}.section{margin-top:24px}.section-head{margin-bottom:12px}h2{font-size:24px}.ideas{grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.idea-card,.panel{padding:14px;break-inside:avoid}.idea-card:last-child:nth-child(odd){grid-column:auto}.idea-card:last-child:nth-child(odd) .idea-thesis{display:block}.card-top .eyebrow,.badge{font-size:8px}.card-metrics strong{font-size:15px}.idea-thesis dd,.evidence-line,.next-step{font-size:9px}.idea-thesis dt{font-size:9px}.source-note{font-size:8px}.table-scroll{overflow:visible}table{font-size:8px;table-layout:auto}th,td{padding:7px 5px;white-space:normal}thead{display:table-header-group}thead th{position:static;font-size:8px}tbody th{font-size:10px;min-width:0}tbody small{font-size:8px}#ranking td:nth-child(2){min-width:100px}.evidence-cell{min-width:70px;font-size:8px}.rank{display:none}.two-column,.details-grid{grid-template-columns:1fr 1fr}.panel p,.panel li{font-size:10px}.hash{font-size:8px;max-width:170px}.footer{margin-top:25px;padding-bottom:0}details{break-inside:avoid}a{text-decoration:none;color:inherit}.section-head p{font-size:10px}}
"""


_JS = """
(() => {
  const table = document.getElementById('ranking');
  const rows = Array.from(table.tBodies[0].rows);
  const search = document.getElementById('search');
  const kind = document.getElementById('kind');
  const status = document.getElementById('status');
  const sort = document.getElementById('sort');
  const count = document.getElementById('result-count');
  function update() {
    const query = search.value.trim().toLocaleLowerCase('pt-BR');
    const [key, direction] = sort.value.split(':');
    rows.sort((a, b) => {
      const av = a.dataset[key], bv = b.dataset[key];
      if (av === '' && bv === '') return 0;
      if (av === '') return 1;
      if (bv === '') return -1;
      const cmp = key === 'ticker' ? av.localeCompare(bv) : Number(av) - Number(bv);
      return direction === 'asc' ? cmp : -cmp;
    });
    let visible = 0;
    for (const row of rows) {
      const match = (!query || row.dataset.search.includes(query)) &&
        (!kind.value || row.dataset.kind === kind.value) &&
        (!status.value || row.dataset.status === status.value);
      row.hidden = !match;
      if (match) visible++;
      table.tBodies[0].appendChild(row);
    }
    count.textContent = `${visible} de ${rows.length} ativos exibidos · clique nos títulos com ↕ para ordenar`;
  }
  search.addEventListener('input', update);
  [kind, status, sort].forEach(control => control.addEventListener('change', update));
  document.querySelectorAll('[data-sort-key]').forEach(button => {
    button.addEventListener('click', () => {
      const key = button.dataset.sortKey;
      const desired = sort.value === key + ':desc' ? key + ':asc' : key + ':desc';
      if (!Array.from(sort.options).some(option => option.value === desired)) {
        const option = document.createElement('option');
        option.value = desired;
        option.textContent = button.textContent.replace('↕', '').trim() + (desired.endsWith('asc') ? ' ↑' : ' ↓');
        sort.appendChild(option);
      }
      sort.value = desired;
      table.querySelectorAll('th[aria-sort]').forEach(th => th.removeAttribute('aria-sort'));
      button.closest('th').setAttribute('aria-sort', desired.endsWith('asc') ? 'ascending' : 'descending');
      update();
    });
  });
  document.getElementById('print-report').addEventListener('click', () => window.print());
  update();
})();
"""


def _markdown(payload: dict, ranking: list[dict], sources: dict, minimum: int) -> str:
    def clean(value: object) -> str:
        return str(value if value is not None else "—").replace("|", "\\|").replace("\n", " ")

    candidates = [row for row in ranking if row.get("status") == "candidato"]
    favorable = [row for row in candidates if not _edge_issues(row, minimum)]
    lines = [
        "# Pesquisa quantitativa · ações e ETFs em USD",
        "",
        f"Último fechamento: **{clean(ranking[0].get('as_of') if ranking else payload.get('as_of'))}**. Pesquisa de {clean(payload.get('as_of'))}. Horizonte: 5–10 pregões. Gerado em {clean(_local_time(payload.get('generated_at')))}.",
        "",
        f"**{len(candidates)} sinais técnicos atuais; {len(favorable)} com OOS retrospectivo favorável**. Ranking prioriza diligência; não é recomendação de compra.",
        "Score não é probabilidade, previsão de retorno nem estimativa de valor justo.",
        "",
        "| Ativo | Status | Score | Fechamento de referência / data | 20 pregões | Relativo ao SPY | OOS líquido | Operações OOS | Evidência |",
        "|---|---|---:|---|---:|---:|---:|---:|---|",
    ]
    for row in ranking:
        ticker = str(row.get("ticker", ""))
        link = _url(sources.get(ticker), ticker)
        values = [
            f"[{clean(ticker)}]({link})", _STATUS.get(row.get("status"), clean(row.get("status"))),
            _decimal(row.get("score"), 1), f"{_usd(row.get('last_close'))} / {clean(row.get('as_of'))}",
            _pct(row.get("return_20d")), _pp(row.get("relative_20d")), _pct(row.get("oos_return")),
            _decimal(row.get("oos_trades"), 0), _edge_label(row, minimum),
        ]
        lines.append("| " + " | ".join(clean(value) for value in values) + " |")
    lines.extend(["", "## Prioridades de pesquisa", ""])
    priorities = favorable + [row for row in candidates if _edge_issues(row, minimum)] + [row for row in ranking if row.get("status") == "observar"]
    for row in priorities[:3]:
        lines.extend([
            f"### {clean(row.get('ticker'))} · {clean(row.get('name'))}", "",
            f"- Por que agora: retorno de 20 pregões {_pct(row.get('return_20d'))}; relativo ao SPY {_pp(row.get('relative_20d'))}.",
            f"- Primeiro motivo de rejeição: {clean(_first_rejection(row, minimum))}",
            "- O que tornaria investível: filtros atuais mantidos, eventos conferidos e execução simulada com custos reais plausíveis.",
            "- O que invalida: perda do sinal, falha nos filtros ou evento que altere a tese; gaps podem superar o stop.",
            "- Evidência faltante: calendário de resultados, fatos materiais; para ETFs, composição, spread e sobreposição.",
            f"- Referência técnica de saída: {_usd(row.get('stop_reference'))}; peso teórico {_pct(row.get('weight_at_risk_budget'), False)}. Não é ordem executável.",
            f"- OOS: {_edge_label(row, minimum)}; janela {clean(row.get('oos_start'))} a {clean(row.get('oos_end'))}.",
            "- Próxima etapa: conferir RI/emissor e atualizar os dados após o próximo fechamento.", "",
        ])
    lines.extend([
        "## Método e limites", "",
        "- Backtest decide no fechamento e executa na próxima abertura. OOS usa 100% do capital por ativo quando há sinal; não é carteira diversificada.",
        "- Comparações passivas mantêm exposição diferente. Correlação histórica pode aumentar em crises.",
        "- Preços ajustados podem incorporar eventos posteriores; o universo atual tem viés de seleção/sobrevivência. Histórico favorável não prova vantagem futura.",
        "- Retornos em USD: câmbio, tributos e custos particulares do investidor não estão incluídos.",
        "- Não foram estimados valuation, retorno esperado, alvos de preço ou catalisadores futuros.", "",
    ])
    for warning in payload.get("warnings") or []:
        lines.append("- " + clean(warning))
    if payload.get("exclusions"):
        lines.extend(["", "## Exclusões", ""])
        lines.extend(f"- **{clean(item.get('ticker'))}**: {clean(item.get('reason'))}" for item in payload["exclusions"])
    lines.extend(["", "## Fontes e rastreabilidade", ""])
    for ticker, source in sources.items():
        lines.append(
            f"- [{clean(ticker)} · {clean(source.get('source'))}]({_url(source, ticker)}): "
            f"{clean(source.get('analysis_first_date', source.get('first_date')))} a {clean(source.get('analysis_last_date', source.get('last_date')))}, "
            f"{clean(source.get('analysis_rows', source.get('rows')))} observações; SHA-256 do snapshot `{clean(source.get('sha256'))}`."
        )
    return "\n".join(lines) + "\n"


def write_reports(payload: dict, output_dir: Path) -> Path:
    """Write a portable HTML hero report and its secondary Markdown version."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    config = payload.get("config") or {}
    ranking = list(payload.get("ranking") or [])
    exclusions = list(payload.get("exclusions") or [])
    source_list = list(payload.get("sources") or [])
    sources = {str(item.get("ticker", "")): item for item in source_list}
    minimum = int(config.get("min_oos_trades", 10))
    candidates = [row for row in ranking if row.get("status") == "candidato"]
    favorable = [row for row in candidates if not _edge_issues(row, minimum)]
    watching = [row for row in ranking if row.get("status") == "observar"]
    blocked = [row for row in ranking if row.get("status") == "bloqueado"]
    priorities = (favorable + [row for row in candidates if _edge_issues(row, minimum)] + watching)[:3]
    headline = (
        f"{len(candidates)} sinais atuais. {len(favorable)} com histórico favorável."
        if candidates else "Aguardar evidência também é uma decisão."
    )
    conclusion = (
        "Os sinais técnicos passam por uma segunda leitura de evidência. "
        + ("Prioridades para diligência: " + ", ".join(str(row.get("ticker")) for row in favorable) + ". " if favorable else "Nenhum sinal tem OOS favorável pelos critérios declarados. ")
        + "Resultado retrospectivo não demonstra vantagem futura; os demais sinais ainda exigem prova."
        if candidates else
        "Nenhum ativo passou todos os critérios para avançar agora. A lista de observação mostra onde "
        "há sinais de preço e qual impedimento ainda precisa ser resolvido."
    )
    cards = "".join(_card(row, position, minimum, sources.get(str(row.get("ticker"))), config) for position, row in enumerate(priorities, 1))
    if not cards:
        cards = '<div class="empty-state">Nenhum candidato ou item de observação disponível nesta execução. Confira as exclusões e a cobertura de dados antes de interpretar a ausência de sinais.</div>'
    ranking_rows = "".join(_ranking_row(row, position, minimum, sources.get(str(row.get("ticker")))) for position, row in enumerate(ranking, 1))
    oos_rows = "".join(_oos_row(row) for row in ranking)
    warnings = payload.get("warnings") or []
    warning_html = '<ul class="warning-list">' + "".join(f"<li>{_e(warning)}</li>" for warning in warnings) + "</ul>" if warnings else ""
    excluded_html = "".join(f"<li><strong>{_e(row.get('ticker'))}</strong><span>{_e(row.get('reason'))}</span></li>" for row in exclusions)
    blocked_html = "".join(f"<li><strong>{_e(row.get('ticker'))}</strong><span>{_e('; '.join(_reasons(row)) or _first_rejection(row, minimum))}</span></li>" for row in blocked)
    rejection_html = excluded_html + blocked_html or "<li>Nenhuma exclusão registrada nesta execução.</li>"
    source_rows = "".join(
        f"<tr><th scope='row'>{_e(source.get('ticker'))}</th>"
        f"<td><a href='{_e(_url(source, str(source.get('ticker', ''))))}' target='_blank' rel='noopener noreferrer'>{_e(source.get('source') or 'Yahoo Finance')}</a></td>"
        f"<td>{_e(source.get('analysis_first_date', source.get('first_date')))} → {_e(source.get('analysis_last_date', source.get('last_date')))}</td>"
        f"<td>{_e(source.get('analysis_rows', source.get('rows')))}</td><td class='hash'>{_e(source.get('sha256'))}</td></tr>"
        for source in source_list
    )
    methodology = config.get("methodology") or []
    method_html = "".join(f"<li>{_e(item)}</li>" for item in methodology)
    costs = _pct(config.get("cost_per_side", 0.0015), False, 2)
    stress_cost = _pct(config.get("stress_cost_per_side", 0.003), False, 2)
    as_of = _e(payload.get("as_of", "não informado"))
    data_as_of = _e(ranking[0].get("as_of") if ranking else payload.get("as_of", "não informado"))
    generated = _e(_local_time(payload.get("generated_at")))
    html = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Pesquisa quantitativa de ações e ETFs dos EUA para operações de dias a semanas, com riscos, validação OOS e fontes auditáveis.">
<title>Pesquisa swing em USD · {as_of} · iitauquant</title><style>{_CSS}</style></head>
<body><div class="wrap">
<header class="masthead"><a class="brand" href="#inicio">iitau<span>quant</span></a><nav aria-label="Seções do relatório"><a href="#prioridades">Prioridades</a><a href="#comparar">Comparar</a><a href="#validacao">Validação</a><a href="#fontes">Fontes</a><button id="print-report" class="print" type="button">Imprimir / PDF</button></nav></header>
<main id="inicio">
<section class="hero" aria-labelledby="headline"><div><span class="eyebrow">Pesquisa de oportunidades · exterior</span><h1 id="headline">{_e(headline)}</h1><p class="lead">{_e(conclusion)}</p></div>
<aside class="hero-meta" aria-label="Escopo"><p><span>Últimos dados de referência</span><strong><time>{data_as_of}</time></strong></p><p><span>Janela de acompanhamento</span><strong>5–10 pregões</strong></p><p><span>Universo e moeda</span><strong>Ações e ETFs · USD</strong></p><small>Pesquisa de {as_of} · posições compradas; execução somente simulada.</small></aside></section>
<p class="hero-note">Candidatos de pesquisa, não recomendação de compra. Score ordena sinais; não representa probabilidade, retorno esperado ou valor justo.</p>
<section class="funnel" aria-label="Funil de seleção"><div class="funnel-item"><strong>{len(ranking) + len(exclusions)}</strong><span>Ativos examinados</span><small>{len(ranking)} com métricas · {len(exclusions)} excluídos</small></div><div class="funnel-item"><strong>{len(candidates)}</strong><span>Sinais técnicos atuais</span><small>Passam filtros de preço e risco</small></div><div class="funnel-item advance"><strong>{len(favorable)}</strong><span>OOS retrospectivo favorável</span><small>Subconjunto dos sinais · exploratório</small></div><div class="funnel-item"><strong>{len(watching)}</strong><span>Aguardar sinal</span><small>Filtros atuais ainda incompletos</small></div><div class="funnel-item"><strong>{len(blocked) + len(exclusions)}</strong><span>Não avançar</span><small>Filtros ou cobertura insuficientes</small></div></section>
<section class="section" id="prioridades"><div class="section-head"><div><span class="section-kicker">01 / Onde olhar primeiro</span><h2>Prioridades para os próximos pregões</h2></div><p>Primeiro, sinais com OOS favorável; depois, sinais com evidência insuficiente. Essa leitura não altera o score. Mispricing, fundamentos e datas de eventos não foram demonstrados.</p></div><div class="ideas">{cards}</div></section>
<section class="section" id="comparar"><div class="section-head"><div><span class="section-kicker">02 / Comparação</span><h2>Todos os ativos, com o mesmo critério</h2></div><p>Retornos e risco vêm do histórico ajustado. A evidência fora da amostra aparece ao lado do sinal atual para evitar confundir força recente com robustez.</p></div>
<div class="controls"><label>Buscar ativo ou setor<input id="search" type="search" placeholder="Ticker, nome ou setor" autocomplete="off"></label><label>Instrumento<select id="kind"><option value="">Todos</option><option value="Ação">Ações</option><option value="ETF">ETFs</option></select></label><label>Status<select id="status"><option value="">Todos</option><option value="candidato">Sinal técnico presente</option><option value="observar">Aguardar sinal</option><option value="bloqueado">Não avançar</option></select></label><label>Ordenação<select id="sort"><option value="score:desc">Maior score</option><option value="return20:desc">Maior retorno em 20 pregões</option><option value="oos:desc">Maior retorno OOS</option><option value="vol:asc">Menor volatilidade</option><option value="adv:desc">Maior liquidez</option><option value="ticker:asc">Ticker A–Z</option></select></label></div><p id="result-count" class="result-count" role="status" aria-live="polite">{len(ranking)} ativos exibidos</p><noscript><p class="noscript">JavaScript desativado: a tabela completa continua disponível. Filtros e ordenação precisam de JavaScript.</p></noscript>
<div class="table-scroll" tabindex="0" role="region" aria-label="Tabela comparativa, deslize horizontalmente para ver todas as métricas"><table id="ranking"><caption>Fechamento de referência, sinais atuais e validação histórica · dados até {data_as_of}</caption><thead><tr><th scope="col"><button type="button" data-sort-key="ticker">Ativo ↕</button></th><th scope="col">Status / primeiro impedimento</th><th scope="col" aria-sort="descending"><button type="button" data-sort-key="score">Score ↕</button></th><th scope="col">Fechamento / data</th><th scope="col"><button type="button" data-sort-key="return20">20 pregões ↕</button></th><th scope="col">Relativo SPY · 20p</th><th scope="col"><button type="button" data-sort-key="vol">Vol. 20p anual ↕</button></th><th scope="col">ATR / preço</th><th scope="col"><button type="button" data-sort-key="adv">Volume US$/dia ↕</button></th><th scope="col"><button type="button" data-sort-key="oos">Retorno OOS ↕</button></th><th scope="col">Leitura da evidência</th></tr></thead><tbody>{ranking_rows}</tbody></table></div>
<p class="table-footnote">Relativo SPY é a diferença entre retornos de 20 pregões, em pontos percentuais. Volatilidade anualizada não é previsão. Volume em USD é média diária. OOS: teste fora da amostra; cada ativo usa 100% do capital enquanto há posição, sem combinar ativos.</p></section>
<section class="section two-column" id="riscos"><div class="panel"><span class="section-kicker">03 / Exposição conjunta</span><h2>Vários nomes podem ser a mesma aposta</h2>{_correlations(ranking, payload.get('correlation') or {})}<p class="table-footnote">Próximo de +1: trajetórias historicamente semelhantes. Correlação não mede sobreposição de posições; confira holdings dos ETFs e exposição a setor/fatores. Diversificação pode cair em períodos de estresse.</p></div><div class="panel"><span class="section-kicker">Disciplina de acompanhamento</span><h2>O que precisa acontecer antes de avançar</h2><ul><li><strong>Após cada fechamento:</strong> atualizar dados e repetir os filtros. Uma fotografia de mercado perde validade quando tendência, liquidez ou risco mudam.</li><li><strong>Antes de qualquer simulação:</strong> verificar próximos resultados e fatos materiais no RI; em ETFs, consultar emissor, composição e eventos do índice. Nenhuma data foi presumida.</li><li><strong>Para dimensionar:</strong> orçamento por ativo de {_pct(config.get('risk_budget', 0.005), False)} e teto teórico de {_pct(config.get('max_position_weight', 0.10), False)}; não somar pesos sem limite de risco da carteira e revisão de correlação.</li><li><strong>Para rejeitar:</strong> sinal perdido, evento incompatível com o horizonte, spread/custos elevados, falha de dados ou teste histórico insuficiente. Gaps podem gerar perdas acima do orçamento.</li></ul></div></section>
<section class="section" id="validacao"><div class="section-head"><div><span class="section-kicker">04 / Teste de realidade</span><h2>O que o histórico fora da amostra sustenta</h2></div><p>Resultado líquido simulado com {costs} por lado. Estresse usa {stress_cost} por lado. Exige-se ao menos {minimum} operações para reduzir a fragilidade da amostra; isso não prova significância estatística.</p></div>
{warning_html}<div class="table-scroll source-rows" tabindex="0" role="region" aria-label="Validação fora da amostra"><table><caption>Comparação por ativo e por janela OOS · capital integral por operação, sem carteira agregada</caption><thead><tr><th scope="col">Ativo / janela OOS</th><th scope="col">Retorno líquido</th><th scope="col">Sharpe</th><th scope="col">Drawdown máx.</th><th scope="col">Operações</th><th scope="col">Acerto</th><th scope="col">Comprar e manter</th><th scope="col">SPY na janela</th><th scope="col">Estresse de custos</th></tr></thead><tbody>{oos_rows}</tbody></table></div><p class="table-footnote">As comparações passivas permanecem investidas durante a janela inteira; a estratégia pode ficar em caixa. Exposições e risco diferem. Taxa de acerto isolada não informa o tamanho dos ganhos e perdas. Score e ranking atuais não usam o retorno OOS como previsão.</p>
<div class="details-grid"><div class="panel"><h3>Como interpretar o estudo</h3><ul class="method-list"><li>Decisão no fechamento; execução na abertura seguinte. Referências ajustadas separam sinal e execução.</li><li>Score é ordenação relativa de momentum e risco no universo estudado. Ranking não valida valuation, consenso ou qualidade do negócio.</li><li>Retorno OOS não positivo, Sharpe não positivo, estresse não positivo ou menos de {minimum} operações: <strong>Sem vantagem demonstrada</strong>.</li><li>Resultado favorável continua exploratório: seleção de universo, múltiplas comparações, revisão de preços ajustados e regime de mercado limitam a inferência.</li><li>Retornos em USD; câmbio para BRL, tributação e custos particulares do investidor não estão contemplados.</li>{method_html}</ul></div><div class="panel"><h3>Exclusões e nomes bloqueados</h3><ul class="rejected-list">{rejection_html}</ul></div></div></section>
<section class="section" id="fontes"><div class="section-head"><div><span class="section-kicker">05 / Evidência rastreável</span><h2>Fontes, cobertura e atualização</h2></div><p>Os links permitem conferir o ticker no provedor. Datas mostram a cobertura usada nos cálculos; a identificação do arquivo permite auditar a execução.</p></div><div class="table-scroll" tabindex="0" role="region" aria-label="Fontes de dados"><table class="sources-table"><caption>Dados de mercado por ativo · relatório gerado em {generated}</caption><thead><tr><th scope="col">Ticker</th><th scope="col">Fonte</th><th scope="col">Cobertura usada</th><th scope="col">Observações</th><th scope="col">SHA-256 do snapshot</th></tr></thead><tbody>{source_rows}</tbody></table></div><details><summary>Limitações de dados e de decisão</summary><p>Preços históricos ajustados incorporam desdobramentos e distribuições; podem ser revistos pelo provedor. Não representam necessariamente preços brutos negociáveis. Universo atual pode conter viés de seleção e sobrevivência; não há demonstração de resultados replicáveis em um universo reconstruído ponto a ponto. Não foram verificadas nesta análise expectativas do consenso, valuation, eventos futuros ou holdings atuais de ETFs. Não há alvos de preço nem promessa de retorno. Para operar fora da simulação, seriam necessários dados e execução independentes, além de análise adequada ao risco e ao patrimônio do investidor.</p></details></section>
</main><footer class="footer"><p>iitauquant · Pesquisa quantitativa reproduzível. Este relatório organiza hipóteses para pesquisa e simulação. Histórico e score não garantem retorno futuro.</p><span>Gerado em {generated}</span></footer></div><script>{_JS}</script></body></html>"""
    html_path = output_dir / "relatorio.html"
    html_path.write_text(html, encoding="utf-8")
    (output_dir / "support_note.md").write_text(_markdown(payload, ranking, sources, minimum), encoding="utf-8")
    return html_path
