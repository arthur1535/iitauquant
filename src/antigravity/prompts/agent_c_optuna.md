# Agente C — Comparação Optuna local

Você implementa/executa uma alternativa Optuna ao grid search sem alterar o motor econômico compartilhado. Pode escrever apenas em `src/optimization/**`, `results/optuna/**` e `logs/optuna/**`. Não use storage, dashboard, sampler ou serviço cloud pago.

## Requisitos

1. Reutilize a mesma função de backtest, universo, custos, calendário e partição temporal do grid search; não duplique a lógica de fills.
2. Otimize somente no bloco In-Sample de 70%. O OOS de 30% fica bloqueado até o estudo e a regra de seleção terminarem.
3. Defina ranges e distribuições antes da execução, seed determinística e sampler/pruner locais. Use SQLite local ou journal local para retomada.
4. Penalize configurações com poucas operações, dados inválidos ou risco extremo de forma declarada. Registre tentativas falhas, não as descarte silenciosamente.
5. Faça smoke test e depois use orçamento de trials/tempo explicitamente configurado. Limite paralelismo para não competir de forma destrutiva com o Agente A.

## Comparação justa

Compare Optuna e grade pelo mesmo orçamento computacional ou reporte claramente a diferença. Mostre número de avaliações, tempo, melhor objetivo IS, distribuição das tentativas, resultado OOS único, drawdown, turnover, estabilidade e sensibilidade local. Não retune após olhar o OOS.

Grave estudo/configuração/seed/commit em `results/optuna/<run_id>/` e logs em `logs/optuna/<run_id>/`. Se a API Optuna instalada divergir da esperada, consulte a documentação local/pacote e ajuste de modo compatível; não instale plano ou serviço adicional.

