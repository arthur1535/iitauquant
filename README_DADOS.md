# Agente de Dados — pipeline auditável

Esta pasta agora tem uma camada executável para coleta, normalização, cache e auditoria dos dados dos três sleeves. O desenho separa o que veio da fonte (`dados/cache`), o que foi normalizado (`dados/processed`) e o diagnóstico (`dados/relatorios`). Cada dataset recebe um sidecar `.meta.json` com fonte, horário, esquema, hash e alertas metodológicos; cada download ou falha entra no log append-only `dados/manifest.jsonl`.

## Fontes e decisões

| Dado | Fonte principal | Regra importante |
|---|---|---|
| Preços e preços ajustados | Yahoo Finance via `yfinance` | `Close` e `Adj Close` são preservados; retornos usam apenas `adjusted_close` |
| Fundamentos | SEC EDGAR Company Facts | A data disponível é `availability_date` (`filed`), não o fim do exercício |
| Spread de crédito | FRED `BAMLH0A0HYM2` ou arquivo licenciado | Diário convertido para o último valor observado de cada mês |
| FF5 + Momentum | Kenneth R. French Data Library | Percentuais convertidos para decimais; `-99.99`/`-999` viram ausentes |
| Holdings de ETF | Arquivo baixado do gestor | Todo snapshot precisa de `as_of`; um arquivo atual não é composição histórica |
| S&P 500 | Tabela pública atual | `point_in_time=false`; o alerta de viés de sobrevivência é obrigatório |

TradingView Premium é útil para conferir visualmente preços, eventos corporativos e símbolos suspeitos. Ele não entra como fonte automatizada: além da reprodutibilidade menor, exportações/scraping podem depender do plano e dos termos da plataforma. Se houver divergência, registre-a no manifesto e confirme contra uma segunda fonte antes de alterar dados.

**Restrição descoberta em julho de 2026:** o próprio FRED informa que, desde abril de 2026, `BAMLH0A0HYM2` contém apenas os três anos mais recentes. Isso não cobre 2015-16 nem 2020 e, portanto, não serve sozinho para a calibração planejada. A auditoria marca `insufficient_history` como erro. Se o TradingView Premium permitir exportar legalmente o histórico completo do símbolo, baixe o CSV pela interface e ingira-o assim:

```powershell
python -m iitauquant_data fred --file "C:\caminho\BAMLH0A0HYM2.csv" --source-label "TradingView Premium exportado manualmente"
python -m iitauquant_data audit
```

## Uso rápido

No PowerShell, a partir da raiz do projeto:

```powershell
python -m pip install -e .
python -m iitauquant_data reference
python -m iitauquant_data audit
```

O comando `reference` coleta S&P 500 atual, IWM/VB/IJR/SPY/BIL, FRED e FF5+Momentum. Para atualizar o cache, acrescente `--refresh`.

Fundamentos exigem que a SEC consiga identificar o pesquisador:

```powershell
$env:SEC_USER_AGENT = "Nome da equipe email@dominio.com"
python -m iitauquant_data fundamentals
```

Sem `--tickers`, esse comando usa a amostra diversificada de 20 empresas definida em `config/dados.json`. Para o universo completo:

```powershell
python -m iitauquant_data fundamentals --tickers "AAPL,MSFT,BRK-B"
```

Holdings baixados do site oficial do gestor são normalizados assim:

```powershell
python -m iitauquant_data holdings --file "C:\caminho\holdings.csv" --fund VB --as-of 2026-07-20
```

Se o nome da coluna não for detectado, use `--ticker-column "Ticker"`.

## Contrato dos dados

- Frequência de modelagem: mensal, fechada no último dia de calendário, com `date` preservando o último pregão observado nos preços.
- Tickers: forma canônica em `ticker`; forma específica do Yahoo em `provider_ticker` (`BRK.B` → `BRK-B`).
- Ausentes: nunca são imputados. O relatório identifica a ausência e o ticker-período deve sair do ranking.
- Fundamentos: em qualquer rebalanceamento, filtre `availability_date <= data_de_decisao`. Isso implementa *point-in-time* pela data real do filing e é mais rigoroso do que uma defasagem fixa de três meses.
- Cache: por padrão, uma coleta existente é reaproveitada. Use `--refresh` conscientemente e preserve o manifesto quando congelar resultados.
- Universo: a composição atual não pode ser apresentada como histórica. Para remover o viés de sobrevivência é necessário adquirir/reconstruir constituintes por data; snapshots atuais apenas documentam o viés.

## Saídas de auditoria

`dados/relatorios/qualidade_dados.csv` lista cada problema com severidade, código, ticker e período. `dados/relatorios/resumo_qualidade.json` dá o status agregado:

- `PASS`: nenhum problema detectado;
- `PASS_WITH_WARNINGS`: utilizável com limitações declaradas;
- `FAIL`: erro estrutural, como dataset ausente, frequência errada, chave duplicada ou preço ajustado inválido.

Rode os testes sem dependência adicional:

```powershell
python -m unittest discover -s tests -v
```
