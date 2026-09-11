param([string]$RepoRoot = (Split-Path -Parent $PSScriptRoot))

$ErrorActionPreference = 'Stop'

function Test-ImporterProcess($Process) {
    # Require a Python executable and the actual script argument, not a word in
    # an unrelated command, browser URL or diagnostic PowerShell command.
    if ($Process.Name -notmatch '^(python(w)?([0-9.]+)?|py)\.exe$') { return $false }
    $tokens = @([regex]::Matches([string]$Process.CommandLine, '"[^"]*"|[^\s"]+') |
        ForEach-Object { $_.Value.Trim('"') })
    for ($i = 1; $i -lt $tokens.Count; $i++) {
        if ($tokens[$i] -match '^-(c|m)') { return $false }
        if ($tokens[$i].StartsWith('-')) { continue }
        return ($tokens[$i] -match '^(?:.*[\\/])?jamroom_importer_server\.py$')
    }
    return $false
}

function Stop-VerifiedProcess($Snapshot) {
    $live = Get-CimInstance Win32_Process -Filter "ProcessId = $($Snapshot.ProcessId)"
    if ($null -ne $live) {
        if ($live.CreationDate -ne $Snapshot.CreationDate) {
            throw "Process $($Snapshot.ProcessId) changed identity; refusing to stop it."
        }
        Stop-Process -Id $live.ProcessId -Force -ErrorAction Stop
    }
}

function Restart-Importer {
    $root = (Resolve-Path -LiteralPath $RepoRoot).Path
    $listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
        Where-Object LocalPort -eq 8765)
    if ($listeners.Count -eq 0) {
        Write-Host 'No importer is running; start JamRoom Importer.bat when needed.'
        return
    }
    $processes = @(Get-CimInstance Win32_Process)
    $owners = @($listeners.OwningProcess | Sort-Object -Unique)
    $targets = @()
    foreach ($ownerId in $owners) {
        $owner = $processes | Where-Object ProcessId -eq $ownerId
        if ($null -eq $owner -or -not (Test-ImporterProcess $owner)) {
            throw "Port 8765 belongs to unverified process $ownerId. It was NOT stopped."
        }
        $targets += $owner
    }
    # Snapshot children before stopping parents. Identity checks prevent killing
    # a recycled PID, and creation times exclude older, unrelated orphan processes.
    $tree = @($targets)
    for ($i = 0; $i -lt $tree.Count; $i++) {
        $parent = $tree[$i]
        $tree += @($processes | Where-Object {
            $_.ParentProcessId -eq $parent.ProcessId -and
            $_.CreationDate -ge $parent.CreationDate -and
            $_.ProcessId -notin $tree.ProcessId
        })
    }
    Write-Host 'Stopping the old importer and its workers. Any unfinished import is interrupted.'
    foreach ($process in $tree) {
        Write-Host "  Stopping $($process.Name), PID $($process.ProcessId)"
        Stop-VerifiedProcess $process
    }
    $deadline = [DateTime]::UtcNow.AddSeconds(10)
    do {
        $remaining = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
            Where-Object LocalPort -eq 8765)
        if ($remaining.Count -eq 0) { break }
        Start-Sleep -Milliseconds 200
    } while ([DateTime]::UtcNow -lt $deadline)
    if ($remaining.Count -ne 0) { throw 'Port 8765 did not become available; importer was not restarted.' }

    $python = Join-Path $env:LocalAppData 'Programs\Python\Python312\python.exe'
    $arguments = @('-u', ('"' + (Join-Path $root 'tools\jamroom_importer_server.py') + '"'))
    if (-not (Test-Path -LiteralPath $python)) {
        $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($launcher) {
            $python = $launcher.Source
            $arguments = @('-3') + $arguments
        } else {
            $python = (Get-Command python.exe -ErrorAction Stop).Source
        }
    }
    $logs = Join-Path $root 'imports\.runtime'
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'
    $stdout = Join-Path $logs "importer-$stamp.stdout.log"
    $stderr = Join-Path $logs "importer-$stamp.stderr.log"
    $started = Start-Process -FilePath $python -ArgumentList $arguments -WorkingDirectory $root `
        -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds(20)
    do {
        try {
            $info = Invoke-RestMethod 'http://127.0.0.1:8765/api/runtime' -TimeoutSec 2
            $listenerIds = @(Get-NetTCPConnection -State Listen -ErrorAction Stop |
                Where-Object LocalPort -eq 8765 | Select-Object -ExpandProperty OwningProcess)
            $live = Get-CimInstance Win32_Process -Filter "ProcessId = $($info.pid)"
            if ($info.app -eq 'jamroom-importer' -and $info.source -eq $root -and
                $info.pid -in $listenerIds -and $null -ne $live -and
                ($live.ProcessId -eq $started.Id -or $live.ParentProcessId -eq $started.Id)) {
                Write-Host "Importer restarted: $($info.build), PID $($info.pid)."
                Write-Host 'Open or refresh http://localhost:8765'
                Write-Host "Startup logs: $logs"
                return
            }
        } catch { }
        Start-Sleep -Milliseconds 250
    } while ([DateTime]::UtcNow -lt $deadline)
    throw "Importer did not confirm startup. Check $stderr and $stdout."
}

# Dot-sourcing exposes functions for isolated tests without stopping anything.
if ($MyInvocation.InvocationName -ne '.') {
    try {
        & (Join-Path $PSScriptRoot 'ensure_importer_dependencies.ps1')
        Restart-Importer; exit 0
    }
    catch { Write-Host "IMPORTER RECOVERY FAILED: $($_.Exception.Message)"; exit 1 }
}
