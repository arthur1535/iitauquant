# Arquitetura do sistema Momentum ATR

## Pesquisa e validação

```text
manifesto point-in-time + OHLCV ajustado
                 |
                 v
      validação de qualidade/proveniência
                 |
                 v
sinal no fechamento t -> ordem pendente -> execução no open t+1
                 |
                 v
 grid/Optuna IS 70% -> seleção -> OOS 30% e walk-forward
                 |
                 v
 métricas, DSR, stress e checkpoints reproduzíveis
```

O preço de decisão e o preço de execução são eventos distintos. Stops usam
OHLC: se a abertura cruza o stop, a execução ocorre na abertura; caso contrário
um toque intradiário executa no nível do stop. Os custos padrão são 0,15% na
entrada e 0,15% na saída.

## Alertas e OMS simulado

```text
TradingView
   | POST JSON (sem segredo do OMS)
   v
Cloudflare Worker
   |-- allowlist de IP e limite de corpo
   |-- HMAC SHA-256 sobre os bytes exatos do JSON
   v
Cloudflare Tunnel / origem HTTPS
   v
FastAPI
   |-- compare_digest + timestamp/nonce do payload
   |-- schema/allowlist/limites/idempotência
   |-- evento append-only em SQLite WAL
   v
Paper OMS (sem adaptador de corretora)
```

O gateway foi preparado, mas não implantado. Isso evita exposição prematura e
qualquer risco de cobrança. O FastAPI deve responder em menos de três segundos;
persistência e retorno são síncronos e pequenos, enquanto análises pesadas ficam
fora do caminho do webhook.

## Fronteiras de confiança

1. Alertas do TradingView são entrada não confiável.
2. Somente o Worker conhece a origem pública; somente Worker e FastAPI conhecem
   o segredo HMAC compartilhado.
3. SQLite é o livro de auditoria local, não uma confirmação de execução real.
4. IBKR e qualquer outro broker ficam deliberadamente fora do processo.
5. Dados de mercado só são aceitos como reais quando possuem proveniência;
   séries sintéticas são marcadas como cenários de teste.
