"""Suporte reproduzível do relatório NU de 28/09/2026; sem ordens de negociação."""
from pathlib import Path
import json
import sys
import hashlib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from strategies.momentum_atr import build_momentum_atr_signals
from backtest.engine import run_backtest, ExecutionConfig

OUT = Path(__file__).resolve().parent
P, N, OUTSTANDING = 12.34, 4.904837, 4.830688659
EQUITY, H1, FY25, H125 = 13.249670, 1.932255, 2.868892, 1.194041
FX_GBP = 1.325  # hipótese coerente com faixa USD do briefing, não spot
monzo_ni = .0863 * FX_GBP  # lucro reportado FY26; inclui efeito fiscal próprio
ttm = FY25 - H125 + H1
model = {'units': 'US$ bilhões salvo preço/EPS, bps e percentuais',
         'price_user_anchor': P, 'shares_diluted_q2_weighted_bn': N,
         'shares_outstanding_june30_bn': OUTSTANDING,
         'equity_parent_june30_bn': EQUITY, 'net_income_parent_h1_bn': H1,
         'ttm_parent_bn': ttm, 'market_cap_computed_bn': P*OUTSTANDING,
         'pb': P*OUTSTANDING/EQUITY, 'pe_ttm_cap': P*OUTSTANDING/ttm,
         'gbpusd_assumption': FX_GBP, 'monzo_reported_net_usd_bn': monzo_ni,
         'forecasts': [], 'deal_sensitivity': [], 'pdd_sensitivity': [], 'scenarios': []}

for e26 in [4.0, 4.3, 4.6]:
    e27 = e26 * 1.14
    model['forecasts'].append({'net_income_2026':e26, 'h2_required':e26-H1,
        'h2_avg_quarter':(e26-H1)/2, 'eps2026':e26/N, 'pe2026':P*N/e26,
        'net_income2027_14pct':e27, 'eps2027':e27/N, 'pe2027':P*N/e27})

# Bridge EPS neutro: S_AT = E0 * novas_acoes/N + custo_caixa_AT + custos - lucro_alvo.
for deal in [10.6, 13.25]:
    for stock_fraction in [0., .5, 1.]:
        new_n = deal*stock_fraction/P
        cash = deal*(1-stock_fraction)
        opportunity = cash*.04
        e0 = 4.3
        e1 = e0 + monzo_ni - opportunity
        model['deal_sensitivity'].append({'deal':deal,'stock_fraction':stock_fraction,
          'new_shares':new_n,'new_shares_pct_of_old':100*new_n/N,
          'ownership_dilution_pct':100*new_n/(N+new_n),'cash':cash,
          'cash_opportunity_aftertax_4pct':opportunity,'eps2026_runrate':e1/(N+new_n),
          'eps_delta_pct':100*((e1/(N+new_n))/(e0/N)-1),
          'synergy_aftertax_for_eps_neutral':e0*new_n/N+opportunity-monzo_ni})
        row=model['deal_sensitivity'][-1]
        e27=4.902
        row['eps2027_runrate']=(e27+monzo_ni-opportunity)/(N+new_n)
        row['eps2027_delta_pct']=100*(row['eps2027_runrate']/(e27/N)-1)
        row['synergy_aftertax_for_eps2027_neutral']=e27*new_n/N+opportunity-monzo_ni

for br_share in [.8, 1.0]:
    for bps in [10,25,50,100]:
        pretax=39.4*br_share*bps/10000
        model['pdd_sensitivity'].append({'br_share_assumption':br_share,'annual_bps':bps,
            'pdd_pretax_bn':pretax,'net_benefit_bn':pretax*.65,
            'eps_delta':pretax*.65/N,'pct_base2026':100*pretax*.65/4.3})

# Preços ao fim de 2026 sobre lucro normalizado/run-rate de 2027, não previsão GAAP pro forma.
cases = [
 ('Bear',4.0,4.2,13.25,1.,.05,.15,12),
 ('Base',4.3,4.902,11.925,.5,.20,.10,16),
 ('Bull',4.6,5.9,0.,0.,0.,0.,17),
]
for name,e26,e27,deal,stock_fraction,synergy,cost,multiple in cases:
    new_n=deal*stock_fraction/P
    cash=deal*(1-stock_fraction)
    added_ni=monzo_ni if deal else 0
    combined=e27+added_ni+synergy-cost-cash*.04
    eps=combined/(N+new_n)
    target=eps*multiple
    model['scenarios'].append(dict(case=name,e2026_standalone=e26,e2027_standalone=e27,
       deal=deal,stock_fraction=stock_fraction,shares_proforma=N+new_n,cash=cash,
       monzo_ni=added_ni,synergy_aftertax=synergy,cost_aftertax=cost,
       cash_drag=cash*.04,e2027_runrate_proforma=combined,eps=eps,
       pe=multiple,target=target,return_pct=100*(target/P-1),
       bdr_constant_fx=target*10.68/P))

df=pd.read_parquet(ROOT/'data/market/ROXO34.SA.parquet')
closed=df[df.index <= pd.Timestamp('2026-09-25')]
signals=build_momentum_atr_signals(closed)
res=run_backtest(df, execution_config=ExecutionConfig(initial_capital=100000))
cut=closed.tail(90).copy()
cut.to_csv(OUT/'roxo34_ohlc_fechado_2026-09-25.csv')
model['technical']={'cache_first':str(df.index.min().date()),'cache_last':str(df.index.max().date()),
   'last_bar_may_be_intraday':True,'closed_bar_date':str(closed.index[-1].date()),
   'closed_price':float(closed.close.iloc[-1]),'atr14_sma':float(signals.atr.iloc[-1]),
   'momentum20':float(signals.momentum.iloc[-1]),'entry_signal':bool(signals.entry_signal.iloc[-1]),
   'local_backtest_reproduced':res.metrics,
   'cache_sha256':hashlib.sha256((ROOT/'data/market/ROXO34.SA.parquet').read_bytes()).hexdigest()}

(OUT/'modelo_sensibilidades.json').write_text(json.dumps(model,indent=2,ensure_ascii=False),encoding='utf-8')
for key in ['forecasts','deal_sensitivity','pdd_sensitivity','scenarios']:
    pd.DataFrame(model[key]).to_csv(OUT/(key+'.csv'),index=False)
print(json.dumps(model,ensure_ascii=False,indent=2))
