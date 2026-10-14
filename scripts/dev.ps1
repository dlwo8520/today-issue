param([ValidateSet('demo', 'live')][string]$Mode = 'demo')
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectDir
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    $portableNode = Get-ChildItem -LiteralPath (Join-Path $projectDir '.tools') -Directory -Filter 'node-*-win-x64' -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
    if (-not $portableNode) {
        python scripts/setup_node.py
        if ($LASTEXITCODE -ne 0) { throw 'Portable Node setup failed.' }
        $portableNode = Get-ChildItem -LiteralPath (Join-Path $projectDir '.tools') -Directory -Filter 'node-*-win-x64' | Sort-Object Name -Descending | Select-Object -First 1
    }
    $env:Path = $portableNode.FullName + ';' + $env:Path
}
if (-not (Test-Path -LiteralPath 'node_modules')) {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
$env:VITE_DATA_MODE = $Mode
npm.cmd run dev
