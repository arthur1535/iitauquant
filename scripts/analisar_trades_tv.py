import pandas as pd
import numpy as np

df = pd.read_csv('dados/tradingview/tradingview_trades_vol_target_export.csv')
saidas = df[df['Tipo'] == 'Saída long'].copy()
entradas = df[df['Tipo'] == 'Entrada long'].copy()

n_trades = len(saidas)
lucros = saidas[saidas['L&P líquido BRL'] > 0]
perdas = saidas[saidas['L&P líquido BRL'] <= 0]

win_rate = len(lucros) / n_trades * 100
total_pnl = saidas['L&P líquido BRL'].sum()
gross_profit = lucros['L&P líquido BRL'].sum()
gross_loss = abs(perdas['L&P líquido BRL'].sum())
profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan

total_fees = saidas['Comissão BRL'].sum()
avg_trade = saidas['L&P líquido BRL'].mean()
avg_win = lucros['L&P líquido BRL'].mean()
avg_loss = perdas['L&P líquido BRL'].mean()
payoff = avg_win / abs(avg_loss) if abs(avg_loss) > 0 else np.nan

capital_inicial = 100000.0
saidas_ord = saidas.iloc[::-1].reset_index(drop=True)
equity_curve = [capital_inicial]
for pnl in saidas_ord['L&P líquido BRL']:
    equity_curve.append(equity_curve[-1] + pnl)
equity_curve = pd.Series(equity_curve)
peaks = equity_curve.cummax()
dds = (equity_curve - peaks) / peaks
max_dd = dds.min() * 100
max_dd_brl = (equity_curve - peaks).min()

stop_exits = saidas[saidas['Sinal'] == 'EXIT_STOP_TRIGGERED']
mom_exits = saidas[saidas['Sinal'] == 'EXIT_MOMENTUM_LOSS']

print(f"Trades Totais: {n_trades}")
print(f"Trades Vencedores: {len(lucros)} ({win_rate:.1f}%)")
print(f"Trades Perdedores: {len(perdas)} ({100 - win_rate:.1f}%)")
print(f"P&L Liquido Total: R$ {total_pnl:,.2f}")
print(f"Lucro Bruto: R$ {gross_profit:,.2f}")
print(f"Prejuizo Bruto: R$ {gross_loss:,.2f}")
print(f"Profit Factor: {profit_factor:.2f}")
print(f"Comissoes Totais: R$ {total_fees:,.2f}")
print(f"Trade Medio: R$ {avg_trade:,.2f}")
print(f"Ganho Medio: R$ {avg_win:,.2f}")
print(f"Perda Media: R$ {avg_loss:,.2f}")
print(f"Payoff Ratio (Ganho/Perda): {payoff:.2f}")
print(f"Max Drawdown: {max_dd:.2f}% (R$ {max_dd_brl:,.2f})")
print(f"Duracao Media: {saidas['Duração (barras)'].mean():.1f} barras")
print(f"Saidas por Stop ATR: {len(stop_exits)} trades | P&L: R$ {stop_exits['L&P líquido BRL'].sum():,.2f} | Win Rate: {(stop_exits['L&P líquido BRL'] > 0).mean()*100:.1f}%")
print(f"Saidas por Perda Momentum: {len(mom_exits)} trades | P&L: R$ {mom_exits['L&P líquido BRL'].sum():,.2f} | Win Rate: {(mom_exits['L&P líquido BRL'] > 0).mean()*100:.1f}%")

print("\n--- Top 3 Maiores Ganhos ---")
for idx, r in lucros.sort_values(by="L&P líquido BRL", ascending=False).head(3).iterrows():
    print(f"Trade #{int(r['Número da negociação'])} ({r['Data e hora']}): +R$ {r['L&P líquido BRL']:,.2f} ({r['Retorno %']:.1f}%) em {int(r['Duração (barras)'])} barras via {r['Sinal']}")

print("\n--- Top 3 Maiores Perdas ---")
for idx, r in perdas.sort_values(by="L&P líquido BRL", ascending=True).head(3).iterrows():
    print(f"Trade #{int(r['Número da negociação'])} ({r['Data e hora']}): R$ {r['L&P líquido BRL']:,.2f} ({r['Retorno %']:.1f}%) em {int(r['Duração (barras)'])} barras via {r['Sinal']}")
