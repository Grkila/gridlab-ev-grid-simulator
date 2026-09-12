param([string]$PythonPath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Invoke-Checked {
    param([string]$Program, [string[]]$Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code ${LASTEXITCODE}: $Program $($Arguments -join ' ')" }
}

try {
    if ($env:OS -ne 'Windows_NT') { throw 'This setup requires Windows.' }
    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    $npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $nodeCommand -or -not $npmCommand) { throw 'Install Node.js 24 with node.exe and npm.cmd on PATH, then open a new terminal.' }
    $node = $nodeCommand.Source
    $npm = $npmCommand.Source
    $nodeVersion = & $node --version
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v24\.') { throw 'Install Node.js 24, then run setup again.' }
    $pythonCheck = "import struct,sys; assert sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8, 'Install 64-bit Python 3.11.'"
    if (Test-Path -LiteralPath $python) {
        Invoke-Checked $python @('-c', $pythonCheck)
    } else {
        if ($PythonPath) {
            $bootstrap = (Resolve-Path -LiteralPath $PythonPath).Path
        } else {
            $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
            if (-not $launcher) { throw 'Install 64-bit Python 3.11, or supply -PythonPath with its python.exe path.' }
            $bootstrap = & $launcher.Source -3.11 -c 'import sys; print(sys.executable)'
            if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 was not found. Install it, then run setup again.' }
            $bootstrap = "$bootstrap".Trim()
        }
        Invoke-Checked $bootstrap @('-c', $pythonCheck)
        Write-Host 'Creating the repository environment...'
        Invoke-Checked $bootstrap @('-m', 'venv', (Join-Path $repoRoot '.venv'))
    }
    Write-Host 'Installing application and reinforcement-learning dependencies...'
    Invoke-Checked $python @('-m', 'pip', 'install', '--upgrade', 'pip')
    Invoke-Checked $python @('-m', 'pip', 'install', '-e', $repoRoot, '-r', (Join-Path $repoRoot 'requirements-rl.txt'))
    Invoke-Checked $python @('-m', 'pip', 'check')
    Invoke-Checked $python @('-c', "import mvgrid.novi_sad.playground_app.server, torch, gymnasium, stable_baselines3; print('Application and RL imports passed.')")
    Write-Host 'Building the application and presentation...'
    Invoke-Checked $npm @('--prefix', (Join-Path $repoRoot 'web'), 'ci')
    Invoke-Checked $npm @('--prefix', (Join-Path $repoRoot 'web'), 'run', 'build')
    Write-Host 'Setup completed. Start with: powershell -ExecutionPolicy Bypass -File scripts/start.ps1'
    exit 0
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
