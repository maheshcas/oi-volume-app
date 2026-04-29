$ErrorActionPreference = "SilentlyContinue"

$logsDir = "C:\Users\Maheswar\OneDrive\Desktop\oi-volume-app\logs"

$latest = Get-ChildItem $logsDir -Filter "signal_report_*.txt" |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1

if ($latest -and (Test-Path $latest.FullName)) {
  Start-Process notepad.exe -ArgumentList $latest.FullName
}
