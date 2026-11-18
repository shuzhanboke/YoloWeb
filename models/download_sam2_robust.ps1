#!/usr/bin/env pwsh
# Supervisor for download_sam2_robust.py
#
# Runs the Python downloader for one SAM2.1 weight at a time and restarts it
# with HTTP-Range resume whenever the on-disk .part file stops growing for
# STALL_SEC seconds (GitHub's release CDN often stalls mid-transfer on slow
# links). Because the downloader resumes from the actual .part size via Range,
# a restart never re-downloads data already on disk.

param(
    [string]$Target = "",
    [string[]]$Only = @()
)

$ErrorActionPreference = "Stop"
$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Target = if ($Target) { $Target } else { $ScriptRoot }
$Py = Join-Path $ScriptRoot "..\.venv\Scripts\python.exe"
if (-not (Test-Path $Py)) { $Py = "python" }

$names = if ($Only.Count) { $Only } else {
    'sam2.1_t.pt', 'sam2.1_s.pt', 'sam2.1_b.pt', 'sam2.1_l.pt'
}
$stallSec = 40
$env:PYTHONDONTWRITEBYTECODE = "1"

foreach ($name in $names) {
    $dest = Join-Path $Target $name
    $part = "$dest.part"
    Write-Output "========== $name =========="
    # loop until finished
    while ($true) {
        $existed = Test-Path $part
        $prev = if ($existed) { (Get-Item $part).Length } else { 0 }
        $proc = Start-Process -FilePath $Py -ArgumentList @($ScriptRoot + "\download_sam2_robust.py", $name) `
            -NoNewWindow -PassThru -RedirectStandardOutput (Join-Path $Target "last_out.txt") `
            -RedirectStandardError (Join-Path $Target "last_err.txt")
        $lastProg = $prev
        $frozen = $false
        while (-not $proc.HasExited) {
            Start-Sleep -Seconds 10
            if (Test-Path $part) {
                $cur = (Get-Item $part).Length
                if ($cur -ne $lastProg) { $lastProg = $cur }
                elseif ((Get-Date) -gt $proc.StartTime.AddSeconds($stallSec)) {
                    $frozen = $true
                    break
                }
            }
        }
        if (-not $proc.HasExited -and $frozen) {
            Write-Output "  [stall] restarting $name (resume)"
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        } elseif ($proc.HasExited) {
            $code = $proc.ExitCode
            Write-Output "  exited code=$code"
            if ((Test-Path $dest) -and (Get-Item $dest).Length -ge 1000) {
                Write-Output "  [done] $name"
                break
            } else {
                Write-Output "  [re-run] $name"
                Start-Sleep -Seconds 2
            }
        }
    }
}
Write-Output "=== ALL DONE ==="