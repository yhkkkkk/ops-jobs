$$ErrorActionPreference = "Stop"

$$InstallDir = "$INSTALL_DIR"
$$BinaryName = "$BINARY_NAME"
$$ServiceName = "$SERVICE_NAME"
$$DisplayName = "$DISPLAY_NAME"
$$DownloadUrl = "$DOWNLOAD_URL"
$$ConfigB64 = "$CONFIG_B64"
$$BinaryPath = Join-Path $$InstallDir $$BinaryName
$$ConfigDir = Join-Path $$InstallDir "config"
$$ConfigPath = Join-Path $$ConfigDir "config.yaml"

if ([string]::IsNullOrWhiteSpace($$ConfigB64)) {
    throw "The installation script does not contain an embedded Agent configuration."
}

$$existingService = Get-Service -Name $$ServiceName -ErrorAction SilentlyContinue
if ($$existingService) {
    if ($$existingService.Status -ne "Stopped") {
        Stop-Service -Name $$ServiceName -Force
    }
    & sc.exe delete $$ServiceName | Out-Null
    Start-Sleep -Seconds 1
}

New-Item -ItemType Directory -Force -Path $$InstallDir, $$ConfigDir | Out-Null
$$packagePath = Join-Path $$env:TEMP ("$$ServiceName-" + [guid]::NewGuid().ToString() + ".pkg")

try {
    Invoke-WebRequest -Uri $$DownloadUrl -OutFile $$packagePath -UseBasicParsing
    if ($$DownloadUrl -match "\\.zip(\\?|$$)") {
        Expand-Archive -Path $$packagePath -DestinationPath $$InstallDir -Force
    }
    else {
        Copy-Item -Path $$packagePath -Destination $$BinaryPath -Force
    }
}
finally {
    if (Test-Path $$packagePath) {
        Remove-Item -Path $$packagePath -Force
    }
}

if (-not (Test-Path $$BinaryPath)) {
    $$candidate = Get-ChildItem -Path $$InstallDir -Recurse -File |
        Where-Object { $$_.Name -in @($$BinaryName, "agent.exe", "agent-server.exe") } |
        Select-Object -First 1
    if (-not $$candidate) {
        throw "The Agent package does not contain $$BinaryName."
    }
    Copy-Item -Path $$candidate.FullName -Destination $$BinaryPath -Force
}

[IO.File]::WriteAllBytes($$ConfigPath, [Convert]::FromBase64String($$ConfigB64))

New-Service -Name $$ServiceName -BinaryPathName ("`"$$BinaryPath`" start") -DisplayName $$DisplayName -StartupType Automatic
Start-Service -Name $$ServiceName

$$service = Get-Service -Name $$ServiceName
if ($$service.Status -ne "Running") {
    throw "$$DisplayName did not reach the Running state."
}

Write-Output "$$DisplayName installed successfully."