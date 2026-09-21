# Governança de dados e viés de sobrevivência

`yfinance` pode auxiliar em protótipos com ativos atuais, mas não prova que o
universo histórico é livre de viés. Um estudo elegível para conclusão deve ter:

- constituintes do universo conhecidos em cada data;
- ativos deslistados, incorporados, falidos e com negociação interrompida;
- datas de início/fim de listagem;
- preços e volumes ajustados com política documentada para dividendos, splits e
  grupamentos;
- timezone/calendário B3 e controle de barras ausentes;
- fonte, data de coleta, licença, checksum e versão do arquivo;
- separação explícita entre dados reais e cenários sintéticos de stress.

O loader deve falhar de forma visível quando um arquivo real estiver ausente;
não é permitido substituir silenciosamente um ativo por uma caminhada aleatória.
Até existir uma base B3 point-in-time completa, os resultados devem ser
rotulados como pesquisa preliminar.

## Stress mínimo

- gap de abertura abaixo do stop;
- sequência prolongada de quedas;
- volatilidade e spread multiplicados;
- liquidez reduzida e custo maior;
- ativo interrompido/delistado com término explícito da série;
- permutação ou deslocamento temporal usado apenas como placebo estatístico.
