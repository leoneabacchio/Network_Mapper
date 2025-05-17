# schedule.ps1 — place this in E:\Oussama\Studies\M2\PFE\Network_Mapper\agents\

# 1. Define where Python and your agent script live
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$pythonExe  = Join-Path $scriptRoot 'windows\venv\Scripts\python.exe'
$agentScript = Join-Path $scriptRoot 'windows\windows_agent.py'

# 2. Create the action
$Action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument $agentScript

# 3. Create a trigger: start 1 min from now, repeat every 1 min for 30 days
$startTime = (Get-Date).AddMinutes(1)
$Trigger = New-ScheduledTaskTrigger `
    -Once -At $startTime `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 30)

# 4. (Optional) Settings to allow it to run if the user isn’t logged in
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

# 5. Register (use -Force to overwrite if it already exists)
Register-ScheduledTask `
    -TaskName "NetworkMapperAgent" `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -RunLevel Highest `
    -Description "Runs the Windows network‐mapper agent every minute"

Write-Host "Scheduled task 'NetworkMapperAgent' installed. It will start at $startTime and repeat every minute for 30 days."
