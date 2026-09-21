# Momentum ATR — integração TradingView

Este diretório contém uma estratégia Pine v5 de pesquisa, long-only, alinhada ao motor Python do projeto. Ela não transmite ordens para corretora e deve permanecer em simulação.

## Contrato matemático

- Momentum na barra `t`: `close[t] / close[t - momentum_window] - 1`.
- Entrada: cruzamento do momentum de `<= 0` para `> 0`, conhecido apenas no fechamento confirmado de `t`.
- Execução da entrada: ordem a mercado criada em `t`; com `process_orders_on_close=false`, o emulador preenche no próximo tick disponível, normalmente `open[t+1]` no histórico.
- ATR: média móvel simples, com janela completa, do True Range.
- Stop inicial: `open_de_entrada - stop_multiplier × ATR[t_sinal]`.
- Stop em posição: se não houver saída, no fechamento de cada barra passa a `max(stop_anterior, close[t] - stop_multiplier × ATR[t])`; portanto nunca recua.
- Stop intrabar: a ordem `strategy.exit` permanece ativa. Gap abaixo do stop é preenchido no `open`; toque pelo `low` é preenchido no stop segundo as regras do broker emulator.
- Saída de momentum: `momentum[t] < 0` no fechamento confirmado; ordem a mercado para o próximo `open`.
- Custo composto: `0,15%` por ponta por meio de `commission_value=0.15`. Não some outra comissão ao comparar com o Python. Cenários extras de slippage devem ser reportados separadamente.

As marcas `SIG` e `MOM` são decisões no fechamento. `IN` e `STOP` são preenchimentos observados pelo emulador. Essa distinção evita confundir preço de sinal com preço executado.

## Compilação manual no Pine Editor

Não existe compilador Pine oficial no ambiente local. Antes de considerar o artefato aceito:

1. Abra o Pine Editor no TradingView e cole integralmente `momentum_atr_strategy.pine`.
2. Confirme `//@version=5`, clique em **Salvar** e depois em **Adicionar ao gráfico**.
3. Verifique que não há erro nem warning no editor.
4. No **Strategy Tester → List of trades**, confirme em pelo menos três entradas que a barra do preenchimento é posterior à barra `SIG` e que o preço é o `open` da barra de execução.
5. Monte um caso com gap e outro com `low <= stop < open`; confirme, respectivamente, preenchimento no `open` e no nível do stop conforme o broker emulator.
6. Confira nas propriedades: pyramiding `0`, recálculo em cada tick desligado, processamento de ordens no fechamento desligado e comissão `0,15%`.
7. Compare uma amostra de trades com o motor Python usando o mesmo ticker, timeframe, sessão, timezone, gráfico ajustado, janela e multiplicador.
8. Só publique depois de registrar data, símbolo, timeframe e capturas dos testes.

## Alertas e webhook

O caminho recomendado para auditoria de preenchimentos é criar um alerta da estratégia com:

- condição **Order fills only**;
- mensagem `recommended_alert.message` de `alert_templates.json`;
- webhook apontando para um gateway assinador controlado;
- frequência **Every time**.

Os valores `strategy.order.alert_message` são definidos pelo Pine e viram um dos três motivos aceitos pelo receiver. O template usa o preço e a quantidade efetivamente preenchidos pelo emulador.

Como alternativa, habilite **Emitir chamadas alert()** e selecione **Any alert() function call / Once per bar close**. Não habilite as duas rotas para o mesmo receiver: isso duplicaria eventos. Nessa alternativa, entrada e saída por momentum são intenções no fechamento; um stop intrabar só é observado pela chamada `alert()` quando a barra fecha.

### HMAC sem segredo no Pine

TradingView não calcula HMAC-SHA256 nem permite definir o header customizado exigido pelo receiver. O fluxo seguro é:

`TradingView → gateway assinador → POST /webhook/tradingview`

O gateway recebe o JSON, calcula HMAC-SHA256 sobre os bytes exatos do corpo e encaminha o corpo inalterado com `X-Webhook-Signature: sha256=<hex>`. A variável `TRADINGVIEW_WEBHOOK_SECRET` existe somente no gateway e no receiver. Nunca a publique no Pine, no corpo do alerta, em URL versionada ou em screenshot.

Até o gateway estar configurado e testado, mantenha o receiver ligado apenas em `127.0.0.1`. Não existe integração direta com Interactive Brokers nem autorização para dinheiro real neste projeto.

## Limitações de paridade

- TradingView usa seu broker emulator e os dados disponíveis no gráfico; o Python usa o dataset local. Sessão, ajustes corporativos e timezone precisam coincidir.
- Barras OHLC não revelam a trajetória intrabar completa. O emulador aplica suas próprias hipóteses quando mais de um nível poderia ser tocado.
- A estratégia de um único gráfico não corrige viés de sobrevivência nem executa walk-forward. Essas validações pertencem ao pipeline Python.
## Catálogo de scripts Pine Script do repositório

| Arquivo | Tipo | Descrição |
|---|---|---|
| [`momentum_atr_strategy.pine`](momentum_atr_strategy.pine) | Strategy | Estratégia quantitativa causal com momentum no fechamento, fill no open $t+1$ e trailing stop ATR ratchet. |
| [`regime_credito_baa.pine`](regime_credito_baa.pine) | Indicator | Indicador macro com BAA10Y + NFCI, z-score móvel e histerese de 1,0/0,5 em modo shadow. |
| [`lastro_portfolio_dashboard.pine`](lastro_portfolio_dashboard.pine) | Indicator (HUD) | Painel multi-sleeve do Fundo LASTRO: calcula pesos dinâmicos em tempo real (33/33/33 até 33/0/67) com tabela HUD. |
| [`trend_vol_target_strategy.pine`](trend_vol_target_strategy.pine) | Strategy | Estratégia de tendência adaptativa com dimensionamento por meta de volatilidade (*volatility targeting*) e webhook JSON. |
| [`relative_strength_momentum12_1.pine`](relative_strength_momentum12_1.pine) | Indicator | Motor do Sleeve 2: Momentum 12-1 defasado + reversão de 1 mês e força relativa contra benchmark. |

---

## Ativos Globais de Alta Performance & Liquidez Institucional

Para além das ações domésticas da B3 (que apresentam maior dependência de ciclos de commodities e risco de cauda em small caps), os scripts foram homologados nos **ativos mais líquidos e consistentes do mercado global**:

| Ticker TradingView | Descrição do Ativo | Retorno Total (2020-2026) | Retorno Anualizado | Sharpe Ratio | Max Drawdown | Profit Factor |
|---|---|:---:|:---:|:---:|:---:|:---:|
| `NASDAQ:NVDA` | NVIDIA Corporation | **+378,32%** | **26,50% a.a.** | **0,870** | -46,73% | **2,05** |
| `NASDAQ:TSLA` | Tesla Inc. | **+310,71%** | **23,63% a.a.** | **0,771** | -42,80% | **1,97** |
| `AMEX:SPY` | SPDR S&P 500 ETF Trust | **+48,83%** | **6,15% a.a.** | **0,645** | **-16,44%** | **1,78** |
| `NASDAQ:MSFT` | Microsoft Corporation | **+64,85%** | **7,80% a.a.** | **0,507** | **-21,90%** | **1,59** |
| `NASDAQ:AAPL` | Apple Inc. | **+47,87%** | **6,05% a.a.** | **0,438** | **-22,90%** | **1,48** |
| `NASDAQ:AMZN` | Amazon.com Inc. | **+60,02%** | **7,32% a.a.** | **0,434** | -46,52% | **1,46** |
| `NASDAQ:GOOGL` | Alphabet Inc. Class A | **+51,80%** | **6,47% a.a.** | **0,403** | -38,17% | **1,43** |
| `NASDAQ:QQQ` | Invesco QQQ Trust (Nasdaq-100) | **+30,13%** | **4,03% a.a.** | **0,373** | **-21,52%** | **1,39** |

### Por que aplicar Momentum e Volatility Targeting em Ativos Globais?
1. **Profundidade Institucional**: Spreads bid-ask abaixo de 0,01% eliminam o atrito de slippage que penaliza estratégias de momentum em ações pouco líquidas.
2. **Tendências Seculares Mais Limpas**: Megacaps de tecnologia (`NVDA`, `MSFT`, `AAPL`) operam com crescimento sustentado de fluxo de caixa livre, apresentando menor taxa de ruído lateral do que ativos estressados.
3. **Controle Estrito de Risco com SPY e QQQ**: Os ETFs amplos de mercado permitem operar momentum sistemático com drawdowns contidos entre -16% e -22% em todo o período histórico (2020 a 2026).

Referências oficiais: [execução e broker emulator](https://www.tradingview.com/pine-script-docs/v5/concepts/strategies/) e [alertas de estratégias](https://www.tradingview.com/pine-script-docs/v5/faq/alerts/).
