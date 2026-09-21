# Cloudflare ingress (não implantado)

Esta pasta contém um gateway mínimo para a rota pública do TradingView. Nada
aqui cria recursos ou altera a conta Cloudflare automaticamente.

Fluxo proposto:

```text
TradingView -> Worker (rota secreta + allowlist de IP) -> HMAC SHA-256 -> FastAPI via Tunnel
```

O TradingView não cria o header HMAC exigido pelo servidor. A allowlist de IP
identifica a infraestrutura do TradingView, mas não identifica sua conta: outro
cliente do TradingView também utiliza esses IPs. Por isso o Worker exige uma
credencial de ingresso independente na URL configurada no alerta:
`https://SEU-WORKER/webhook/tradingview/INGRESS_ROUTE_SECRET`.
Esse último segmento é o valor secreto, não o nome literal da variável.

`INGRESS_ROUTE_SECRET` deve conter 32 bytes aleatórios codificados em base64url
(43 caracteres sem padding; aceita de 43 a 128 caracteres URL-safe). É uma
credencial limitada ao ingresso de simulações: nunca reutilize o segredo do
OMS, senhas ou credenciais de corretora. Guarde-a somente na configuração
privada do alerta e no secret do Worker, fora do Pine e do versionamento.
O servidor recusa configuração com os dois segredos iguais.

O Worker valida a origem na borda, limita o corpo, assina os bytes exatos do JSON com HMAC-SHA256
em `X-Webhook-Signature` e só então o encaminha ao FastAPI. `timestamp` e
`nonce` permanecem no payload e são validados pelo receptor contra replay. O
segredo HMAC compartilhado nunca aparece no Pine, na URL pública ou no repositório.
O contrato é `HMAC-SHA256(ORIGIN_HMAC_SECRET, raw_body_bytes)`, sem prefixo de
timestamp/nonce e sem reserializar JSON. A origem permanece em
`/webhook/tradingview`; os campos de tempo e nonce do corpo autenticado são
validados pelo FastAPI.

O ingresso lê no máximo 16 KiB por streaming, mesmo sem Content-Length ou com
esse header incorreto. Exige `application/json`, UTF-8 válido e nenhum
Content-Encoding. A origem recebe somente os headers gerados pelo gateway;
cookies e Authorization recebidos não são encaminhados. Redirects são recusados.
A resposta da origem deve ser JSON com até 64 KiB. Erros HTTP de negócio são
preservados, falha de rede retorna 502, e timeout da origem retorna 504.

O orçamento é 2 segundos para receber a resposta completa da origem e 2,5
segundos para o handler inteiro, incluindo leitura de corpo. Isso reserva uma
margem para o limite de 3 segundos do TradingView, mas não garante o prazo de
rede ponta a ponta. Timeout pode ocorrer após uma ordem simulada ter sido
gravada: confira o ledger por idempotency_key; qualquer repetição deve manter
essa chave. O gateway não gera nova chave nem declara sucesso em timeout.

O código registra apenas tipo de evento, request_id, código de erro e status.
Logs automáticos de invocação e traces estão desligados porque podem registrar
a URL com a credencial. Antes de publicar, verifique também logs de acesso,
exportações, regras e ferramentas de monitoramento da conta: uma rota secreta
é uma credencial bearer e deve ser rotacionada se vazar. Não use screenshots
da URL privada nem compartilhe configurações de alerta sem ocultá-la.

## Teste local sem conta e sem custo

```powershell
node --test .\infra\cloudflare\test\worker.test.mjs
.\.venv\Scripts\python -m pytest tests/test_gateway_contract.py -q
```

## Implantação futura (ação manual)

1. Confirme que a conta está no plano Workers Free e que não há upgrades ou
   recursos pagos habilitados.
2. Instale o Wrangler apenas quando for implantar e gere os tipos com
   `npx wrangler types`.
3. Defina `ORIGIN_HMAC_SECRET` e `INGRESS_ROUTE_SECRET` como secrets independentes
   com `wrangler secret put`; nunca os coloque no `wrangler.jsonc`.
4. Substitua `ORIGIN_URL` por um hostname HTTPS de origem acessível somente
   pelo túnel. O Tunnel por si só não torna um hostname público privado:
   mantenha HMAC obrigatório na origem e não exponha outras rotas. O Worker
   rejeita credenciais, query string, fragmento e caminho diferente da rota
   de webhook em ORIGIN_URL; HTTP somente é aceito em 127.0.0.1 para teste.
5. Execute `wrangler deploy --dry-run` antes de qualquer deploy real.
6. Mantenha a allowlist sincronizada com a documentação oficial do
   TradingView.

O Quick Tunnel (`trycloudflare.com`) serve apenas para desenvolvimento: a URL
é aleatória e não possui garantia de disponibilidade. Nenhum Worker ou Tunnel
foi provisionado por este projeto, evitando qualquer cobrança ou exposição
acidental.

Os testes Node executam o handler com fetch substituído por uma origem local
falsa. O teste Python usa os bytes e a assinatura realmente produzidos pelo
handler JavaScript em um FastAPI TestClient, sem conexões externas. Ainda são
necessários validação no runtime Workers (workerd/Wrangler), ensaio com
TradingView e revisão da conta antes de exposição pública. Nenhuma conexão
com Interactive Brokers ou execução com dinheiro real é implementada aqui.

Referências consultadas em 07/09/2026: [Workers best practices](https://developers.cloudflare.com/workers/best-practices/workers-best-practices/),
[Web Crypto](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/) e
[TradingView webhooks](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/).
Contrato de APIs revisado com `@cloudflare/workers-types` 5.20260907.1 e schema
de configuração do Wrangler 4.129.0; isso não equivale a deploy validado.
