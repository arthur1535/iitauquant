# Entradas reais necessárias

Os dois templates possuem somente cabeçalhos. `events_research.csv` contém notas
jurídicas para pesquisa, não observações de regulação: não recebe score automático
e não pode ser passado como `regulatory_snapshots`.

`trends.template.csv`: `week_end` é YYYY-MM-DD, último dia completo da semana no
fuso America/Sao_Paulo. A série precisa de frequência semanal, sem lacunas, e cada
semana aparece uma única vez. `available_at` exige ISO8601 com offset e corresponde
ao instante em que a observação daquela vintage estava acessível. `interest` é
índice 0–100; `vintage_id` identifica a extração arquivada. Datas de disponibilidade
não podem diminuir à medida que as semanas avançam. Lotes baixados hoje levam
disponibilidade de hoje e não geram sinais historicamente negociáveis.

Esta versão não implementa reconstrução de revisões: semanas duplicadas são
rejeitadas, mesmo com vintage_id diferente. Cabe ao pesquisador comprovar que o
painel semanal foi arquivado em tempo real; metadados não comprovam sua origem.
Uma série retrospectiva deve ser identificada como tal no relatório do backtest.

`regulatory_snapshots.template.csv`: `available_at` com offset, `regulation_score`
numérico entre -1 e 1, `source` não vazio. O score deve seguir uma rubrica definida
antes de avaliar retornos. Este preparador valida o intervalo, não calibra a
rubrica nem considera endurecimento regulatório prova de liberação de renda.
Cada timestamp deve possuir um único estado documentado.

O programa emite `available_at,search_relief_z,regulation_score,vintage_id` na
união dos instantes das fontes, com merge_asof para trás. O fuso da saída é UTC
explícito. Há NaN enquanto faltar fonte ou histórico; esses valores não permitem
entrada. A diferença atual de log(1+interest) é comparada com média e desvio
amostral das últimas 52 diferenças ANTERIORES, mínimo 26. O sinal é o z-score com
sinal invertido. Desvio zero produz NaN. As primeiras 27 semanas não têm sinal.

O consumidor precisa alinhar `available_at` ao pregão seguinte à decisão e definir
prazo máximo de validade da informação. Não usar backfill e não negociar dado
publicado depois do horário da decisão. Snapshots regulatórios persistem até uma
atualização explícita; isso não comprova que o estado jurídico ficou inalterado.

Timestamps conservadores de fim de dia no arquivo de eventos evitam atribuir à
estratégia uma informação anterior à publicação comprovada. Não representam o
primeiro instante da descoberta pelo mercado. Datas de vigência programada não
são choques independentes; seus available_at ficam vazios deliberadamente.

Google Trends é atenção relativa amostrada e normalizada, não depósitos ou perdas:
https://support.google.com/trends/answer/4365533?hl=en
