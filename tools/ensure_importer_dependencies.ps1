$ErrorActionPreference = 'Stop'
$dependencyScript = Join-Path $PSScriptRoot 'ensure_importer_dependencies.py'
$dependencyPython = Join-Path $env:LocalAppData 'Programs\Python\Python312\python.exe'
if (Test-Path -LiteralPath $dependencyPython) {
    & $dependencyPython $dependencyScript
} elseif (Get-Command py.exe -ErrorAction SilentlyContinue) {
    & py.exe -3 $dependencyScript
} else {
    & python.exe $dependencyScript
}
if ($LASTEXITCODE -ne 0) { throw 'Importer dependencies could not be installed; check the download error above.' }
