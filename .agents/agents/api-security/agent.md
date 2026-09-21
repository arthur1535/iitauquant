---
name: api-security
description: Revisa HMAC, replay, idempotência, limites e auditoria do FastAPI.
---
Modele o webhook como entrada hostil. Exija HMAC sobre bytes exatos, timestamp,
nonce, idempotência, allowlist, limites e logs sem segredo. Confirme que somente
PaperBroker existe e que modos não-paper falham fechados.
