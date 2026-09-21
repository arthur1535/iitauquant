# Momentum ATR — laboratório quantitativo e OMS simulado

Implementação local, reproduzível e **paper-only** de uma estratégia de
momentum com trailing stop por ATR. O projeto separa pesquisa, backtest,
recepção de alertas e simulação de ordens. Nenhum módulo envia ordens a uma
corretora.

## Limites de segurança

- O modo é fixado em `paper` pelo schema; não existe variável ou opção para
  habilitar execução live.
- Credenciais não possuem valor padrão e nunca devem entrar no Git.
- O endpoint público proposto usa allowlist na borda e HMAC entre o gateway e
  o FastAPI.
- Não há deploy automático, criação de chave, assinatura paga ou recurso com
  cobrança variável.
- Resultados de backtest são experimentais e não constituem recomendação de
  investimento.

## Estrutura

```text
src/strategies/       fator de momentum e ATR
src/backtest/         simulação, grid, Optuna e walk-forward
src/server/           FastAPI, auditoria SQLite e OMS paper
src/antigravity/      prompts/manifests para agentes locais
tradingview/          Pine v5 e templates de alerta
infra/cloudflare/     gateway HMAC e exemplo de Tunnel (não implantado)
config/               universo e limites operacionais
data/                 cache OHLCV com proveniência
results/              checkpoints, métricas e banco paper
tests/                testes determinísticos
```

## Instalação no Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-tradingview.txt
.\.venv\Scripts\python.exe -m pip install -e .
```

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pytest
node --test .\infra\cloudflare\test\worker.test.mjs
```

Consulte `docs/ARCHITECTURE_MOMENTUM.md` para o fluxo completo e
`docs/ACCEPTANCE_CHECKLIST.md` para o estado verificável dos critérios.
