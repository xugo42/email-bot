# 切换开机自启：当前开启 -> 关闭，当前关闭 -> 开启
$startup = [Environment]::GetFolderPath('Startup')
$lnk = Join-Path $startup 'MailBot.lnk'
$bot = Join-Path $PSScriptRoot '启动机器人后台.bat'
if (Test-Path $lnk) {
    Remove-Item $lnk -Force
    Write-Host '已关闭开机自启'
} else {
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($lnk)
    $sc.TargetPath = $bot
    $sc.WorkingDirectory = $PSScriptRoot
    $sc.Save()
    Write-Host '已开启开机自启'
}
