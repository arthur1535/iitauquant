# Agentes portáveis para execução local

Este diretório descreve três trabalhos paralelos, mas não presume que exista uma CLI ou SDK chamado “Antigravity”/“Spark”. O manifesto é deliberadamente neutro: pode ser usado como checklist em uma interface de agentes que tenha acesso autorizado ao workspace local.

## Como iniciar sem criar cobrança

1. Confirme no produto escolhido que a execução está coberta pelo plano já existente e não exige API key faturável, crédito, upgrade ou provisionamento cloud. Se a interface mostrar preço, pare.
2. Abra a raiz deste repositório e verifique que o agente enxerga o mesmo `git status` do operador.
3. Crie três sessões no máximo e cole, uma por sessão, os prompts em `prompts/`.
4. Mantenha os escopos de escrita de `manifest.json`. A e C podem consumir CPU em paralelo; B deve concluir a verificação inicial antes de aceitar resultados dos demais.
5. Use dados locais por padrão. Qualquer download precisa ser gratuito, explicitamente permitido e registrado; nunca contorne rate limit.
6. Revise os diffs e relatórios manualmente. Agente concluído não significa resultado quantitativo aprovado.

## Coordenação recomendada

- Inicie B primeiro para obter uma linha de base dos testes.
- Depois rode A e C em paralelo, limitando workers para preservar responsividade do Windows.
- Se A e C precisarem alterar o mesmo módulo central, pause ambos e faça a mudança compartilhada em uma tarefa separada; não aceite duas versões concorrentes.
- Cada agente deve escrever um manifesto de execução no próprio diretório de resultados. Um resultado sem commit de origem, configuração, seed e período de dados não é reproduzível.

Não há automação de login, criação de conta, compra ou consumo de cota incluída aqui. Também não há conexão com Interactive Brokers.

