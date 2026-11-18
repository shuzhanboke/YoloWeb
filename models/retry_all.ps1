#!/usr/bin/env pwsh
# Self-healing downloader: repeatedly runs download_sam2_robust.py over all four
# SAM2.1 weights until every file is complete. Each invocation Range-resumes the
# on-disk .part file, so a GitHub CDN connection drop just costs one restarted
# process, never re-downloaded bytes.

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Join-Path $root "..\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }
$env:PYTHONDONTWRITEBYTECODE = "1"
# Route downloads through the local proxy (v2rayN socks/http on 10808).
$env:HTTPS_PROXY = "http://127.0.0.1:10808"
$env:HTTP_PROXY  = "http://127.0.0.1:10808"
$all = 'sam2.1_t.pt','sam2.1_s.pt','sam2.1_b.pt','sam2.1_l.pt'

for ($round = 0; $round -lt 60; $round++) {
    $doneAll = $true
    foreach ($name in $all) {
        $dest = Join-Path $root $name
        if (Test-Path $dest) {
            $mb = [math]::Round((Get-Item $dest).Length / 1MB, 1)
            Write-Output "[ok] $name ($mb MB)"
            continue
        }
        $doneAll = $false
        Write-Output "--- round $round : $name ---"
        & $py (Join-Path $root "download_sam2_robust.py") $name
        Write-Output "    exit=$LASTEXITCODE"
    }
    if ($doneAll) {
        Write-Output "=== ALL COMPLETE ==="
        break
    }
    Start-Sleep -Seconds 3
}
if (-not $doneAll) {
    Write-Output "!!! GAVE UP after 60 rounds MRZ !!!"
}