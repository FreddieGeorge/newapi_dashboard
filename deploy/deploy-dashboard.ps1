param(
    [string]$Server = $env:NEW_API_DASHBOARD_SERVER,
    [string]$SiteRoot = "/var/www/newapi-dashboard"
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Server)) {
    throw "Server is required. Use -Server user@host or set NEW_API_DASHBOARD_SERVER."
}

$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$IndexFile = Join-Path $RepositoryRoot "index.html"
$VendorDir = Join-Path $RepositoryRoot "vendor"
$EChartsFile = Join-Path $VendorDir "echarts.min.js"
$PapaParseFile = Join-Path $VendorDir "papaparse.min.js"
$RemoteTemp = "$SiteRoot/.dashboard-upload-$PID"
$SshKey = Join-Path $env:USERPROFILE ".ssh\id_ed25519"

foreach ($file in @($IndexFile, $EChartsFile, $PapaParseFile)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Required file not found: $file"
    }
}

$sshOptions = @()
if (Test-Path -LiteralPath $SshKey -PathType Leaf) {
    $sshOptions += @("-i", $SshKey)
}

& ssh @sshOptions $Server "mkdir -p '$RemoteTemp/vendor'"
if ($LASTEXITCODE -ne 0) {
    throw "Could not create remote upload directory."
}

& scp @sshOptions $IndexFile "${Server}:${RemoteTemp}/index.html"
if ($LASTEXITCODE -ne 0) {
    throw "index.html upload failed."
}

& scp @sshOptions $EChartsFile $PapaParseFile "${Server}:${RemoteTemp}/vendor/"
if ($LASTEXITCODE -ne 0) {
    throw "Vendor upload failed."
}

$publishCommand = "mkdir -p '$SiteRoot/vendor' && chmod 644 '$RemoteTemp/index.html' '$RemoteTemp/vendor/'*.js && mv '$RemoteTemp/index.html' '$SiteRoot/index.html' && mv '$RemoteTemp/vendor/'*.js '$SiteRoot/vendor/' && rmdir '$RemoteTemp/vendor' '$RemoteTemp'"
& ssh @sshOptions $Server $publishCommand
if ($LASTEXITCODE -ne 0) {
    throw "Remote publish failed. Check ownership of $SiteRoot."
}

Write-Host "Dashboard files published to ${Server}:${SiteRoot}"
