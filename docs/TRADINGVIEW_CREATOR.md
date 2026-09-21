# Material de publicação — Momentum ATR

## Título sugerido

**Momentum ATR — entrada no próximo candle e proteção adaptativa**

## Resumo curto

Estratégia long-only de pesquisa que combina cruzamento de momentum com trailing stop baseado em ATR. Os sinais usam somente barras fechadas, as ordens de mercado são simuladas no próximo `open` e o relatório incorpora custo composto de 0,15% por ponta.

## Descrição metodológica

O momentum é a variação do fechamento em relação ao fechamento de `n` barras antes. Uma entrada é criada apenas quando esse valor cruza de não positivo para positivo em uma barra confirmada. Como o preço de fechamento só é conhecido ao fim da barra, a estratégia não usa esse mesmo preço como execução: o preenchimento simulado ocorre na abertura seguinte.

O risco é acompanhado por ATR calculado como média móvel simples do True Range. Na entrada, o stop fica a um múltiplo do ATR observado na barra do sinal abaixo do preço efetivamente preenchido. Depois, ele pode apenas subir, usando `max(stop anterior, fechamento − múltiplo × ATR)`. O stop permanece como ordem no emulador, de forma que gaps e toques intrabar são tratados segundo as regras do Strategy Tester. Se o momentum ficar negativo, a saída a mercado também é decidida no fechamento e preenchida na abertura seguinte.

O modelo inclui uma premissa composta de 0,15% por transação de entrada e de saída. Esse número é uma hipótese conservadora agregada para pesquisa; custos, impostos, spreads e slippage reais variam por ativo, corretora, tipo de investidor e condições de mercado.

## Como interpretar o gráfico

- `SIG`: decisão de entrada tomada no fechamento; não é o preço de execução.
- `IN`: preenchimento da entrada pelo broker emulator.
- linha laranja: stop ATR ativo, que não recua durante a posição.
- `MOM`: decisão de saída por momentum no fechamento.
- `STOP`: saída preenchida pelo stop.

O dashboard apresenta posição, momentum, ATR, stop, estimativa de P&L aberto líquido e último evento. Ele é telemetria; não substitui a lista de operações nem o relatório de validação Python.

## Parâmetros

- **Janela de momentum:** horizonte da taxa de variação.
- **Janela do ATR:** número de barras da média simples do True Range.
- **Multiplicador do ATR:** distância e sensibilidade do stop.
- **Quantidade simulada:** tamanho fixo usado apenas pelo Strategy Tester e pelos payloads de simulação.

Não publique parâmetros como “ótimos” sem indicar ativo, período, custos, universo, número de tentativas e resultado fora da amostra. Presets devem ser apresentados como exemplos de pesquisa, não como recomendação.

## Limitações e declaração de risco

Este script é uma ferramenta educacional e de pesquisa. Não constitui recomendação de investimento, consultoria, promessa de rentabilidade, oferta de produto financeiro ou autorização para execução automática. Backtests têm limitações, e desempenho passado não garante resultados futuros. Podem ocorrer perdas, gaps além do stop, indisponibilidade de dados, diferenças de sessão, slippage, baixa liquidez e divergência entre o broker emulator e qualquer mercado real.

“Non-repainting” significa, neste projeto, que decisões usam barras confirmadas e não consultam dados futuros. Isso não elimina viés de seleção, sobreajuste, incerteza intrabar ou revisão de dados. A evidência de robustez — incluindo walk-forward 70/30, cenários adversos e ativos fora do universo vencedor — deve vir do pipeline Python e ser atualizada quando parâmetros ou dados mudarem.

O código atual é estritamente de simulação. Não existe conexão com Interactive Brokers ou outra corretora, nem testes suficientes para uso com capital real.

## Acesso invite-only / Paid Spaces

Antes de publicar, confirme as regras atuais de Scripts, Vendors e Paid Spaces diretamente no TradingView. Use somente os mecanismos de acesso e cobrança permitidos pela plataforma, descreva com clareza o que o assinante recebe e mantenha canal de suporte identificável. Não use resultados hipotéticos como depoimentos, não oculte premissas materiais e não faça alegações de lucro certo, baixo risco ou superioridade não demonstrada.

Texto sugerido para instruções do autor:

> O acesso disponibiliza a estratégia Momentum ATR para estudo no TradingView e sua documentação de uso. Adicione-a a um gráfico compatível, confira os parâmetros e consulte a seção “Como interpretar”. O suporte cobre configuração e metodologia; não fornece recomendação individual nem garantia de desempenho. A automação externa não faz parte do acesso e permanece desabilitada neste projeto.

## Checklist editorial

- Compilação Pine v5 concluída sem erros ou warnings no editor.
- Descrição coincide com o comportamento real do código.
- Comissão de 0,15% por ponta e execução no próximo `open` aparecem de forma visível.
- Capturas não usam cherry-picking sem informar período, ativo e timeframe.
- Resultados mostram In-Sample e Out-of-Sample separadamente.
- Ausência de linguagem de garantia, urgência artificial ou aconselhamento personalizado.
- Política de acesso, suporte, atualização e cancelamento descrita conforme as regras atuais da plataforma.
- Nenhum segredo, endpoint privado, dado pessoal ou credencial em código, imagens ou alertas.

