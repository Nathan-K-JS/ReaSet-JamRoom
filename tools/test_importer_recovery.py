"""Exercise Windows updater recovery with fake OS processes, never real imports."""
import pathlib
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform == 'win32', 'Windows updater')
class RecoveryTests(unittest.TestCase):
    def run_ps(self, script):
        helper = pathlib.Path(__file__).with_name('restart_importer.ps1')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command',
                                 ". '" + str(helper).replace("'", "''") + "'\n" + script + '\nexit 0'],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_identity_requires_python_and_script_argument(self):
        self.run_ps(r'''
$ErrorActionPreference = 'Stop'
foreach ($command in @('python tools/jamroom_importer_server.py',
    '"C:\Program Files\Python\python.exe" -u "C:\Jam Room\tools\jamroom_importer_server.py"')) {
    if (-not (Test-ImporterProcess ([pscustomobject]@{Name='python.exe'; CommandLine=$command}))) {
        throw "Failed to identify $command"
    }
}
foreach ($command in @('python other.py', 'python jamroom_importer_server.py.bak',
    'python -c "print(''jamroom_importer_server.py'')"', 'python -c "# tools/jamroom_importer_server.py"')) {
    if (Test-ImporterProcess ([pscustomobject]@{Name='python.exe'; CommandLine=$command})) {
        throw "Incorrectly identified $command"
    }
}
if (Test-ImporterProcess ([pscustomobject]@{Name='reaper.exe'; CommandLine='jamroom_importer_server.py'})) {
    throw 'Identified REAPER as importer'
}
''')

    def test_no_listener_does_not_start_or_stop_processes(self):
        self.run_ps(r'''
function Get-NetTCPConnection { @() }
function Start-Process { throw 'Unexpected start' }
function Stop-Process { throw 'Unexpected stop' }
Restart-Importer
''')

    def test_unrelated_listener_is_left_alone(self):
        self.run_ps(r'''
function Get-NetTCPConnection { [pscustomobject]@{LocalPort=8765; OwningProcess=42} }
function Get-CimInstance { [pscustomobject]@{ProcessId=42; Name='reaper.exe'; CommandLine='reaper.exe'} }
function Stop-Process { throw 'Unexpected stop' }
try { Restart-Importer; throw 'Expected rejection' }
catch { if ($_.Exception.Message -notlike '*unverified process 42*') { throw } }
''')

    def test_recycled_pid_is_not_killed(self):
        self.run_ps(r'''
function Get-CimInstance { [pscustomobject]@{ProcessId=42; CreationDate=2} }
function Stop-Process { throw 'Unexpected stop' }
try { Stop-VerifiedProcess ([pscustomobject]@{ProcessId=42; CreationDate=1}); throw 'Expected rejection' }
catch { if ($_.Exception.Message -notlike '*changed identity*') { throw } }
''')

    def test_hung_importer_and_children_stopped_before_restart(self):
        self.run_ps(r'''
$script:stopped = @()
$script:restarted = $false
$script:snapshot = @(
    [pscustomobject]@{ProcessId=42; ParentProcessId=1; CreationDate=1; Name='python.exe'; CommandLine='python tools/jamroom_importer_server.py'},
    [pscustomobject]@{ProcessId=43; ParentProcessId=42; CreationDate=2; Name='ffmpeg.exe'},
    [pscustomobject]@{ProcessId=44; ParentProcessId=43; CreationDate=3; Name='worker.exe'},
    [pscustomobject]@{ProcessId=45; ParentProcessId=42; CreationDate=0; Name='unrelated.exe'})
function Get-NetTCPConnection {
    if ($script:restarted) { [pscustomobject]@{LocalPort=8765; OwningProcess=99} }
    elseif (42 -notin $script:stopped) { [pscustomobject]@{LocalPort=8765; OwningProcess=42} }
}
function Get-CimInstance($ClassName, $Filter) {
    if ($Filter -eq 'ProcessId = 99') { return [pscustomobject]@{ProcessId=99; ParentProcessId=1} }
    if ($Filter) { return $script:snapshot | Where-Object { $Filter -eq "ProcessId = $($_.ProcessId)" } }
    return $script:snapshot
}
function Stop-Process($Id) { $script:stopped += $Id }
function New-Item { }
function Start-Process {
    if (($script:stopped -join ',') -ne '42,43,44') { throw 'Wrong process tree stopped' }
    $script:restarted = $true
    [pscustomobject]@{Id=99}
}
function Invoke-RestMethod {
    [pscustomobject]@{app='jamroom-importer'; source=(Resolve-Path $RepoRoot).Path; pid=99; build='test'}
}
Restart-Importer
if (-not $script:restarted) { throw 'Did not restart' }
''')


if __name__ == '__main__':
    unittest.main()
