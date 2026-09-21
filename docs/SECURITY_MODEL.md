# Modelo de segurança do webhook paper-only

## Propriedades obrigatórias

- Falhar ao iniciar se o segredo estiver ausente/fraco; o schema aceita somente
  o modo literal `paper`.
- Autenticar bytes exatos do corpo com HMAC SHA-256.
- Assinar o corpo bruto e comparar o digest com `hmac.compare_digest`; validar
  separadamente o `timestamp` e o `nonce` autenticados dentro desse corpo.
- Rejeitar timestamp expirado, nonce repetido e idempotency key duplicada.
- Validar ticker, ação, motivo, quantidade e notional antes da simulação.
- Nunca registrar segredo, assinatura completa ou corpo bruto.
- Persistir evento recebido, decisão e paper order de forma auditável.
- Oferecer kill switch que rejeita novas ordens sem apagar o histórico.
- Não conter cliente, chave, endpoint ou pacote de corretora.

## Ameaças tratadas

| Ameaça | Controle |
|---|---|
| Origem arbitrária | allowlist na borda |
| Alteração do corpo | HMAC sobre bytes exatos |
| Replay | timestamp, nonce e idempotência |
| Ordem excessiva | limites de quantidade/notional |
| Símbolo inesperado | allowlist local |
| Vazamento de segredo | variáveis/secret store, logs redigidos |
| Exposição da máquina | Tunnel outbound-only |
| Ordem real acidental | persistência paper-only, sem cliente ou adaptador de broker |

Uma varredura Codex Security deve ser executada depois que todos os módulos e
testes estiverem integrados. Achados exigem revisão humana antes de qualquer
deploy público.
