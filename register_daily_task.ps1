$taskName = "FundAnalysisDailyReport"

Write-Host "Automatic trading-day report scheduling is disabled."
Write-Host "This project no longer registers a daily scheduled task."
Write-Host "Run the report manually with:"
Write-Host "  .\\run_daily_report.bat"
Write-Host ""
Write-Host "If this computer already has the old task, remove it with:"
Write-Host "  powershell -ExecutionPolicy Bypass -File .\\unregister_daily_task.ps1"
