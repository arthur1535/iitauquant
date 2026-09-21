# Runbook operacional — pesquisa Momentum ATR

## Limites de operação

O ambiente é **simulation-only**. O receiver registra intenções e preenchimentos simulados em SQLite; ele não deve importar SDK de corretora, possuir chave de trading nem encaminhar ordens reais. `OMS_KILL_SWITCH=true` prevalece sobre qualquer configuração. Nenhuma etapa deste runbook autoriza serviço pago, upgrade de plano ou consumo faturável.

## 1. Preparação local

Na raiz do repositório, use um ambiente virtual dedicado e instale apenas as dependências versionadas pelo projeto. Antes de cada rodada:

```powershell
git status --short
python -m pytest
```

Registre o commit, o arquivo de configuração, o período dos dados e o timezone. Não apague checkpoints ou o banco para “limpar” um resultado; mova-os para uma pasta de arquivo quando necessário.

## 2. Receiver local

Crie um segredo aleatório com pelo menos 32 caracteres e mantenha-o apenas na sessão/gerenciador de segredos. O exemplo abaixo contém um marcador, não um segredo válido:

```powershell
$env:TRADINGVIEW_WEBHOOK_SECRET = '<segredo-aleatorio-com-32+-caracteres>'
$env:OMS_KILL_SWITCH = 'true'
python -m uvicorn src.server.app:app --host 127.0.0.1 --port 8000
```

Configuração opcional: `OMS_SIMULATION_CONFIG` aponta para o JSON da simulação; o padrão é `config/oms_simulation.json`. O `database_path` dessa configuração controla o SQLite, cujo padrão é `data/oms_simulation.sqlite3` e modo WAL.

Pré-voo:

1. `GET http://127.0.0.1:8000/health` responde que o processo está vivo.
2. Com `OMS_KILL_SWITCH=true`, `GET http://127.0.0.1:8000/ready` deve retornar `503/not_ready`; esse é o teste seguro do bloqueio.
3. Depois de confirmar que não existe conector de broker, reinicie com `OMS_KILL_SWITCH=false`; `/ready` deve retornar `200`, `mode=paper` e banco disponível.
4. Payload sem assinatura ou com assinatura inválida recebe `401`.
5. Payload válido assinado recebe `200`; o mesmo `idempotency_key` reenviado não cria uma segunda ordem.
6. Ticker fora da allowlist, quantidade inválida, timestamp antigo/futuro e motivo incompatível são rejeitados.
7. O registro no SQLite contém o evento, decisão de risco e timestamps, mas nunca o segredo.

Mantenha o bind em `127.0.0.1`. Para receber alertas externos, coloque um gateway controlado na frente. Ele deve assinar os bytes exatos do corpo com HMAC-SHA256 e encaminhar `X-Webhook-Signature`. TradingView não produz esse header. Um Tunnel pode transportar a requisição, mas não substitui autenticação, anti-replay, idempotência ou kill switch. Não publique o receiver diretamente.

## 3. TradingView

Siga o checklist de `tradingview/README_MOMENTUM_ATR.md`. Depois da compilação manual:

1. Use o mesmo ticker, timeframe, sessão, timezone e ajuste de proventos do dataset Python.
2. Configure comissão de 0,15% e preserve `process_orders_on_close=false`.
3. Prefira o template **Order fills only** em `tradingview/alert_templates.json`.
4. Configure a URL do gateway fora do código; não coloque segredo na mensagem.
5. Envie primeiro a um ambiente local de teste e confira `401`, `200` e deduplicação.
6. Não combine alertas de order fill e `alert()` no mesmo receiver.

## 4. Execuções paralelas locais

Os artefatos em `src/antigravity/` são portáveis e não dependem de uma CLI inventada. Abra o workspace no orquestrador que já estiver disponível, crie no máximo os três agentes descritos no manifesto e cole o prompt correspondente. Exija confirmação visual do diretório e do modo simulation-only antes de iniciar.

- Agente A escreve checkpoints/resultados do grid search.
- Agente B trabalha na suíte de testes.
- Agente C escreve a implementação/resultados Optuna.

Não dê o mesmo arquivo gravável a dois agentes. Pause uma tarefa se aparecer conflito no Git ou pressão excessiva de CPU/memória. Mais agentes que núcleos/recursos úteis costumam apenas aumentar contenção.

Google Spark não é requisito técnico do pipeline. Sem uma API/CLI local oficialmente disponível e verificada, os prompts podem ser copiados manualmente para uma interface compatível, mas nenhum script deste repositório deve tentar controlar a conta, contratar recursos ou contornar limites do plano.

## 5. Encerramento e evidências

Ao final de uma rodada:

1. Pare alertas no TradingView e depois encerre gateway/receiver.
2. Confirme que não há processo de grid/Optuna ainda ativo.
3. Preserve logs, SQLite, checkpoints, configuração efetiva e relatório de testes.
4. Compare Python e TradingView trade a trade em uma amostra que contenha entrada, stop comum, stop com gap e saída por momentum.
5. Marque o resultado como inválido se houver dado futuro, custo diferente de 15 bps por ponta, parâmetros escolhidos com OOS ou ausência de ativos/cenários adversos.

## Resposta a incidentes

- **Evento inesperado ou duplicado:** ative `OMS_KILL_SWITCH=true`, pare o alerta e preserve banco/logs antes de investigar.
- **Assinatura inválida:** verifique se o gateway assinou o corpo bruto sem reserializar o JSON e se ambos os lados usam o mesmo segredo; nunca imprima o segredo.
- **Divergência Pine/Python:** alinhe dados, sessão, timezone e ajustes; em seguida compare barra de sinal, ATR, preço de fill e stop carregado.
- **Exposição acidental:** derrube o gateway, rotacione segredo e identificador opaco da rota, revise logs e só reabra após novo teste de `401/200`.
- **Qualquer indício de rota para corretora:** mantenha kill switch, remova credenciais do processo e trate como bloqueador. O escopo atual não inclui dinheiro real.
