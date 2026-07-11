$$ErrorActionPreference = "Stop"

$$InstallDir = "$INSTALL_DIR"
$$BackupDir = "$BACKUP_DIR"
$$ServiceName = "$SERVICE_NAME"
$$ConfigPath = Join-Path $$InstallDir "config\config.yaml"

$$service = Get-Service -Name $$ServiceName -ErrorAction SilentlyContinue
if ($$service) {
    if ($$service.Status -ne "Stopped") {
        Stop-Service -Name $$ServiceName -Force
    }
    & sc.exe delete $$ServiceName | Out-Null
    Start-Sleep -Seconds 1
}

if (Test-Path $$ConfigPath) {
    New-Item -ItemType Directory -Force -Path $$BackupDir | Out-Null
    $$timestamp = Get-Date -Format "yyyyMMddHHmmss"
    Copy-Item -Path $$ConfigPath -Destination (Join-Path $$BackupDir ("config.yaml." + $$timestamp + ".bak")) -Force
}

if (Test-Path $$InstallDir) {
    Remove-Item -Path $$InstallDir -Recurse -Force
}

Write-Output "Ops Job Agent uninstall completed."