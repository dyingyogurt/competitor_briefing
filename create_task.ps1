param(
    [Parameter(Mandatory = $true)]
    [string]$TaskDir,

    [Parameter(Mandatory = $true)]
    [string]$Runner,

    [Parameter(Mandatory = $true)]
    [string]$TriggerTime
)

$taskName = "competitor-briefing-daily"

# Build a start boundary using today + TriggerTime
$startBoundary = (Get-Date -Format "yyyy-MM-ddT$TriggerTime`:00")

# Escape values for XML
$runnerXml = [System.Security.SecurityElement]::Escape($Runner)
$taskDirXml = [System.Security.SecurityElement]::Escape($TaskDir)

$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>每天 $TriggerTime 生成竞品日报</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>$startBoundary</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <IdleSettings>
      <StopOnIdleEnd>false</StopOnIdleEnd>
      <RestartOnIdle>false</RestartOnIdle>
    </IdleSettings>
    <RestartOnFailure>
      <Interval>PT10M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$runnerXml</Command>
      <WorkingDirectory>$taskDirXml</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$tempXml = "$env:TEMP\competitor_briefing_task.xml"
# schtasks /xml expects UTF-16 / Unicode
$xml | Out-File -FilePath $tempXml -Encoding Unicode -Force

schtasks /create /tn "$taskName" /xml "$tempXml" /f

if ($LASTEXITCODE -eq 0) {
    Write-Host "定时任务已创建：$taskName（每天 $TriggerTime 执行，已开启 StartWhenAvailable）"
} else {
    Write-Host "创建失败。请确认已使用管理员身份运行脚本。"
}
