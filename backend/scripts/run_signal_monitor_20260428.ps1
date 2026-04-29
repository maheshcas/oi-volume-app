$ErrorActionPreference = "Stop"

$repoRoot = "C:\Users\Maheswar\OneDrive\Desktop\oi-volume-app"
$logsDir = Join-Path $repoRoot "logs"
$reportScript = Join-Path $repoRoot "backend\scripts\signal_monitor_report.py"

if (-not (Test-Path $logsDir)) {
  New-Item -ItemType Directory -Path $logsDir | Out-Null
}

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $logsDir "signal_report_$stamp.txt"

Push-Location $repoRoot
try {
  $report = python $reportScript 2>&1
  $header = @(
    "OptionLens Signal Monitor Report",
    "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz')",
    "File: $outFile",
    ""
  )
  ($header + $report) | Out-File -FilePath $outFile -Encoding UTF8
}
finally {
  Pop-Location
}
