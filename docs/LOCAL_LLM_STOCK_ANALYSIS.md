# LLM local para análise de ações

O repositório inclui um executor local em `scripts/run_local_stock_llm.py`. Ele usa a GPU NVIDIA via PyTorch CUDA, carrega o `Qwen/Qwen2.5-3B-Instruct` quantizado em 4 bits e recebe uma fotografia técnica calculada a partir de dados diários do Yahoo Finance.

## Instalação no Windows

No PowerShell, a partir da raiz do repositório:

```powershell
.\scripts\setup_local_llm.ps1
```

O script instala PyTorch com CUDA 12.4 no `.venv`, depois instala Transformers, Accelerate, bitsandbytes e yfinance. O primeiro uso baixa aproximadamente 6,2 GB de pesos FP16 do Hugging Face e os mantém no cache local; a quantização em 4 bits reduz o uso de VRAM para cerca de 2–3 GiB.

## Executar uma análise

```powershell
.\.venv\Scripts\python.exe scripts\run_local_stock_llm.py --ticker NVDA
.\.venv\Scripts\python.exe scripts\run_local_stock_llm.py --ticker ASHR --period 5y --report results/china_research/relatorio_pesquisa_china.md
```

O programa imprime a GPU usada, o pico de VRAM, os indicadores calculados e a resposta do modelo. O prompt obriga o modelo a separar fatos de inferências e termina em um veredito de triagem, sem gerar ordem ou promessa de retorno.

## Limites de governança

- O modelo não executa ordens, não possui credenciais de corretora e permanece paper-only.
- O snapshot é ajustado e serve para triagem; não substitui os backtests causais, o walk-forward OOS, DSR/PBO ou a diligência fundamentalista.
- A resposta não é recomendação personalizada. Para promover um ativo, registre a hipótese, rode o teste OOS com custos e compare com benchmark.
- Se a VRAM ficar cheia, reduza `--max-new-tokens` para 250 ou use o modelo padrão de 3B; não aumente o contexto sem necessidade.
