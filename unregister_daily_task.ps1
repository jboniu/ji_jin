$taskName = "FundAnalysisDailyReport"

try {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction Stop
    if ($task) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Removed scheduled task: $taskName"
    }
} catch {
    Write-Host "Scheduled task not found: $taskName"
}
