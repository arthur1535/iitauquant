# Snapshot exploratório da tese bets — B3

Dados Yahoo Finance coletados em 28/09/2026, limitados ao último pregão completo de **25/09/2026**. Não são dados sintéticos nem projeções. Reproduzir a coleta a partir da raiz do repositório:

```powershell
.venv\Scripts\python.exe results\bets_research\market\collect_market_snapshot.py
```

Não foi instalada nenhuma dependência. O ambiente existente tem Python 3.12, pandas 3.0.5, numpy 2.5.2 e yfinance 1.7.0. Como statsmodels não está instalado, o script calcula OLS e a matriz HAC Newey–West diretamente com numpy.

## Método

Todos os 13 ativos têm **252 retornos diários pareados entre 23/09/2025 e 25/09/2026**. Retornos simples de Adj Close, sem preenchimento de preços ausentes. Beta = Cov(r_ativo,r_IBOV)/Var(r_IBOV), equivalente à inclinação de OLS com intercepto; mínimo de 200 observações. A coluna de beta semanal usa 52 pares semanais como sensibilidade à frequência. O beta é exposição ao mercado acionário brasileiro; não mede fluxo doméstico nem causalidade da regulação de apostas.

IC95% usa aproximação normal e Newey–West, núcleo Bartlett, 5 defasagens e correção n/(n−2). O IC quantifica incerteza amostral condicional e não cobre mudanças de regime. Não subtraímos CDI dos retornos: este beta é de retornos totais brutos, não uma regressão CAPM de retornos excedentes.

ADV60 é a **estimativa** média de Close × Volume retornados por Yahoo com `auto_adjust=False`, em **60 observações de 03/07/2026 a 25/09/2026**. É proxy de giro em reais; Close × Volume não é o financeiro oficial da B3, pois não usa os preços de cada negócio. Nenhum split foi informado pelo provedor na janela ADV60. Não usamos Adj Close no cálculo de liquidez. Para produção, reconciliar preços, eventos e volumes com B3 ou fonte licenciada.

## Resultado

| Ticker | Beta diário | IC95% HAC | Beta semanal | ADV60 estimado, R$ milhões | Passa filtro técnico + liquidez + beta? |
|---|---:|---:|---:|---:|---|
| LREN3 | 1,415 | 1,243 a 1,587 | 1,229 | 201,4 | Não: SMA200 e momentum12−1 |
| CEAB3 | 1,765 | 1,466 a 2,065 | 1,912 | 76,1 | Não: SMA200 e momentum12−1 |
| RIAA3 | 1,591 | 1,316 a 1,865 | 1,742 | 10,6 | Não: ADV, SMA200 e momentums |
| MGLU3 | 1,958 | 1,604 a 2,313 | 1,976 | 122,1 | Não: beta, SMA200 e momentum12−1 |
| AZZA3 | 1,290 | 0,984 a 1,596 | 0,973 | 44,5 | Não: SMA200 e momentum12−1 |
| VIVA3 | 1,124 | 0,878 a 1,370 | 1,270 | 64,5 | Não: SMA200 e momentums |
| MULT3 | 1,244 | 1,078 a 1,411 | 1,267 | 113,1 | Não: momentum12−1 |
| IGTI11 | 1,293 | 1,111 a 1,475 | 1,135 | 56,7 | Sim, posição 5 do ranking técnico |
| ALOS3 | 1,203 | 1,052 a 1,354 | 1,258 | 118,0 | Sim, posição 2 |
| B3SA3 | 1,599 | 1,431 a 1,766 | 1,277 | 583,1 | Sim, posição 1 |
| BPAC11 | 1,570 | 1,429 a 1,710 | 1,469 | 576,4 | Sim, posição 4 |
| ITUB4 | 1,172 | 1,091 a 1,253 | 1,223 | 938,4 | Sim, posição 3 |
| BBDC4 | 1,206 | 1,125 a 1,287 | 1,267 | 630,1 | Não: SMA200 |

Filtro exploratório solicitado: ADV60 ≥ R$20 milhões; 0,7 ≤ beta252 ≤ 1,8; momentum20 = C[t]/C[t−20]−1 > 0; momentum12−1 = C[t−21]/C[t−252]−1 > 0; C[t] > SMA200. Ranking decrescente por momentum12−1/sigma60, com sigma60 = desvio-padrão amostral dos 60 retornos × √252. Selecionar no máximo seis entre elegíveis; nesta fotografia só cinco passam. Os limiares são regras de pesquisa, não valores estimados como ótimos.

**Passar o filtro técnico não constitui sinal de compra da tese bets.** O estado point-in-time da regulação e da atenção/apostas não foi carregado. Nenhum Sharpe, retorno de estratégia ou ganho causal foi calculado nesta etapa. A composição atual também não deve ser retroaplicada sem tratar viés de sobrevivência.

## Correções de ticker e fontes primárias

- **RIAA3 substituiu GUAR3 em 05/02/2026.** O download usou RIAA3.SA e o histórico anterior já retornado pelo provedor, sem emenda manual. A continuidade dos eventos corporativos deve ser auditada para produção. Fontes: [comunicado RI de 28/01/2026](https://filemanager-cdn.mziq.com/published/0c51b75c-1d63-4db0-85ed-6a34ac67fccc/21ea0526-a74a-4ab8-93f7-a3ee5a9329ca_comunicado_ao_mercado_novo_codigo_de_negociacao.pdf) e [B3, 05/02/2026](https://www.b3.com.br/pt_br/noticias/toque-de-campainha-8AA8D0CD9BC68ADD019C4355713B795D.htm).
- ALOS3, AZZA3, B3SA3, BPAC11, CEAB3 e BBDC4 são confirmados na [prévia IBOV da B3](https://sistemaswebb3-listados.b3.com.br/indexPage/preview/IBOV?language=pt-br). MULT3, IGTI11, VIVA3 e ITUB4 constam do [calendário B3 de balanços do 2T2026](https://borainvestir.b3.com.br/objetivos-financeiros/investir-melhor/temporada-de-balancos-confira-o-calendario-de-divulgacao-dos-resultados-do-segundo-trimestre-2/). LREN3 consta do [cadastro B3 Lojas Renner](https://sistemaswebb3-listados.b3.com.br/listedCompaniesPage/main/8133/CODBOLSA/overview?language=pt-br) e MGLU3 consta do [cadastro B3 Magazine Luiza](https://sistemaswebb3-listados.b3.com.br/listedCompaniesPage/main/22470/MGLU/overview?language=pt-br).
- AZZA3 incorpora eventos das antecessoras ARZZ3 e SOMA3: [circular B3](https://www.b3.com.br/data/files/FE/11/55/95/09BE09105FE89209AC094EA8/OC%20012-2024-VNC%20Tratamento%20Carteiras%20de%20%C3%8Dndices%20da%20B3%20-%20Evento%20de%20Incorpora%C3%A7%C3%A3o%20do%20Grupo%20de%20Moda%20Soma%20pela%20Arezzo_PT.pdf). Não concatenar antecessoras como se fossem empresas economicamente idênticas.
- **INBR32 (Inter), ROXO34 (Nu) e XPBR31 (XP)** são BDRs negociados no Brasil confirmados em [publicação B3 de 2026](https://borainvestir.b3.com.br/tipos-de-investimentos/renda-variavel/bdrs/mercado-brasileiro-ja-negocia-mais-de-r-1-bi-em-bdrs-por-dia/). Podem integrar análise complementar, mas têm exposição a câmbio e ações negociadas no exterior; beta e ADV não foram calculados para eles aqui.

`market_snapshot.csv/json` contém valores sem arredondamento visual, flags, janelas e ranking; `yahoo_daily_snapshot.csv` preserva OHLCV/ações corporativas/Adj Close; `adjusted_close.csv` e `daily_returns.csv` permitem replicar as métricas. `manifest.json` contém metadados, método e hashes SHA256 dos CSVs.

Verificação: todos os ativos têm 252 pares e ADV com 60 observações; nenhum dado obsoleto frente ao IBOV; beta OLS concorda com Cov/Var (diferença máxima abaixo de 5×10⁻¹⁰ após arredondamento do CSV). Os cinco candidatos elegíveis em ordem são B3SA3, ALOS3, ITUB4, BPAC11 e IGTI11.
