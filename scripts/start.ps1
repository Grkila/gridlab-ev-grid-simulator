param(
    [ValidateRange(1, 65535)][int]$Port = 8517,
    [switch]$Presentation,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot '.venv\Scripts\python.exe'
try {
    if ($env:OS -ne 'Windows_NT') { throw 'This launcher requires Windows.' }
    foreach ($required in @($python, (Join-Path $repoRoot 'web\dist\index.html'), (Join-Path $repoRoot 'web\dist\presentation.html'))) {
        if (-not (Test-Path -LiteralPath $required)) { throw 'Setup is incomplete. Run scripts/setup.ps1 first.' }
    }
    & $python -c "import sys,struct; assert sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8; import mvgrid.novi_sad.playground_app.server, torch, gymnasium, stable_baselines3"
    if ($LASTEXITCODE -ne 0) { throw 'The application environment is incomplete. Run scripts/setup.ps1 again.' }
    $launchArgs = @((Join-Path $PSScriptRoot 'run_playground_app.py'), '--port', "$Port")
    if ($Presentation) { $launchArgs += '--presentation' }
    if (-not $NoBrowser) { $launchArgs += '--open-browser' }
    & $python @launchArgs
    exit $LASTEXITCODE
} catch {
    Write-Host "Start failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
