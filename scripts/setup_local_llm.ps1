$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $python)) {
    Write-Host '[local-llm] Criando .venv com Python 3.12...'
    py -3.12 -m venv (Join-Path $repoRoot '.venv')
}

Write-Host '[local-llm] Atualizando pip...'
& $python -m pip install --upgrade pip

Write-Host '[local-llm] Instalando PyTorch com CUDA 12.4...'
& $python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124

Write-Host '[local-llm] Instalando Transformers, quantização e dados...'
& $python -m pip install -r (Join-Path $repoRoot 'requirements-local-llm.txt')

Write-Host '[local-llm] Validando CUDA...'
& $python -c "import torch; assert torch.cuda.is_available(), 'CUDA não está disponível'; print('CUDA:', torch.version.cuda); print('GPU:', torch.cuda.get_device_name(0)); print('VRAM GiB:', round(torch.cuda.get_device_properties(0).total_memory / 2**30, 2))"

Write-Host ''
Write-Host '[local-llm] Ambiente pronto. O primeiro uso baixa ~6,2 GB de pesos FP16; a quantização usa cerca de 2-3 GiB de VRAM.'
Write-Host '[local-llm] Exemplo: .\.venv\Scripts\python.exe scripts\run_local_stock_llm.py --ticker NVDA'
