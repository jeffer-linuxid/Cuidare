$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Ambiente Python não encontrado em $python. Crie .venv e instale desktop\requirements.txt."
}

$buildRoot = Join-Path $env:TEMP "caremanager-pyinstaller"
$workPath = Join-Path $buildRoot "build"
$specPath = Join-Path $buildRoot "spec"
$distPath = Join-Path $projectRoot "dist"
New-Item -ItemType Directory -Force -Path $workPath, $specPath, $distPath | Out-Null

Push-Location $projectRoot
$previousErrorActionPreference = $ErrorActionPreference
try {
    $ErrorActionPreference = "Continue"
    & $python -m PyInstaller `
        --noconfirm `
        --onefile `
        --windowed `
        --name CareManager `
        --paths (Join-Path $projectRoot "desktop") `
        --paths (Join-Path $projectRoot "server") `
        --additional-hooks-dir (Join-Path $projectRoot "desktop\pyinstaller_hooks") `
        --hidden-import app.main `
        --workpath $workPath `
        --specpath $specPath `
        --distpath $distPath `
        (Join-Path $projectRoot "desktop\offline_main.py")
    $buildExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
    Pop-Location
}
if ($buildExitCode -ne 0) {
    throw "PyInstaller encerrou com código $buildExitCode."
}

$executable = Join-Path $distPath "CareManager.exe"
if (-not (Test-Path $executable)) {
    throw "O executável não foi criado em $executable."
}
Write-Output "Executável criado: $executable"
