param([ValidateSet('x64', 'x86')][string]$RuntimeArch = 'x64')
$ErrorActionPreference = 'Stop'
# Official Microsoft runtime for the native Numba wheels. Verify the downloaded
# executable before running it; never fetch individual DLLs from third parties.
$runtimeFolder = Join-Path ([IO.Path]::GetTempPath()) ('reaset-runtime-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $runtimeFolder | Out-Null
$runtimeInstaller = Join-Path $runtimeFolder 'vc_redist.exe'
try {
    Invoke-WebRequest -UseBasicParsing -Uri "https://aka.ms/vc14/vc_redist.$runtimeArch.exe" -OutFile $runtimeInstaller -TimeoutSec 90
    $signature = Get-AuthenticodeSignature -LiteralPath $runtimeInstaller
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation,') {
        throw 'Microsoft runtime signature verification failed.'
    }
    $runtimeProcess = Start-Process -FilePath $runtimeInstaller -ArgumentList '/install', '/passive', '/norestart' -WindowStyle Hidden -Wait -PassThru
    if ($runtimeProcess.ExitCode -notin @(0, 3010, 1638)) {
        throw "Microsoft runtime installer exited $($runtimeProcess.ExitCode)."
    }
    if ($runtimeProcess.ExitCode -eq 3010) { Write-Host 'Windows requests a restart to finish the audio runtime repair.' }
} finally {
    if (Test-Path -LiteralPath $runtimeInstaller) { Remove-Item -LiteralPath $runtimeInstaller }
    Remove-Item -LiteralPath $runtimeFolder
}
