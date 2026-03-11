param(
    [switch]$NoNewWindow
)

$ErrorActionPreference = "Stop"

$backendDir = $PSScriptRoot
$projectRoot = Split-Path -Parent $backendDir
$frontendDir = Join-Path $projectRoot "frontend"

function Stop-PortProcess {
    param([int]$Port)

    $lines = netstat -ano -p tcp | Select-String ":$Port"
    $pids = @()

    foreach ($line in $lines) {
        $parts = ($line.ToString() -split "\s+") | Where-Object { $_ -ne "" }
        if ($parts.Length -ge 5) {
            $pid = $parts[-1]
            if ($pid -match "^\d+$") {
                $pids += [int]$pid
            }
        }
    }

    $pids | Sort-Object -Unique | ForEach-Object {
        try {
            Stop-Process -Id $_ -Force -ErrorAction Stop
            Write-Host "Stopped process on port $Port (PID $_)"
        }
        catch {
            Write-Warning "Could not stop PID $_ on port $Port: $($_.Exception.Message)"
        }
    }
}

if (-not (Test-Path $frontendDir)) {
    throw "Frontend directory not found: $frontendDir"
}

Stop-PortProcess -Port 8000
Stop-PortProcess -Port 5173

$backendCommand = "Set-Location '$backendDir'; python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
$frontendCommand = "Set-Location '$frontendDir'; cmd /c npm run dev"

if ($NoNewWindow) {
    Start-Job -ScriptBlock {
        param($command)
        powershell -NoProfile -Command $command
    } -ArgumentList $backendCommand | Out-Null

    Start-Sleep -Seconds 2

    Start-Job -ScriptBlock {
        param($command)
        powershell -NoProfile -Command $command
    } -ArgumentList $frontendCommand | Out-Null

    Write-Host "Backend and frontend started as background jobs."
}
else {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCommand
    Start-Sleep -Seconds 2
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCommand
    Write-Host "Backend and frontend restart commands launched in new windows."
}
