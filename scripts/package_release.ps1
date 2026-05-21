param(
    [ValidateSet('standard', 'upx')]
    [string]$Variant = 'standard'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..')
$releaseDir = Join-Path $repoRoot 'release'

if ($Variant -eq 'upx') {
    $distDir = Join-Path $repoRoot 'dist_nuitka_upx\HustNetwork_GUI.dist'
    $zipPath = Join-Path $releaseDir 'HustNetwork_GUI_upx.zip'
} else {
    $distDir = Join-Path $repoRoot 'dist_nuitka\HustNetwork_GUI.dist'
    $zipPath = Join-Path $releaseDir 'HustNetwork_GUI.zip'
}

if (-not (Test-Path -LiteralPath $distDir)) {
    throw "Distribution directory not found: $distDir"
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -Path (Join-Path $distDir '*') -DestinationPath $zipPath -Force

$zipItem = Get-Item -LiteralPath $zipPath
$hash = Get-FileHash -LiteralPath $zipPath -Algorithm SHA256

[PSCustomObject]@{
    Variant = $Variant
    ZipPath = $zipItem.FullName
    SizeMB = [math]::Round($zipItem.Length / 1MB, 2)
    SHA256 = $hash.Hash
}
