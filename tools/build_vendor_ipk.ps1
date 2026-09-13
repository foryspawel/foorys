param(
    [Parameter(Mandatory = $true)]
    [string]$SourceRoot,
    [Parameter(Mandatory = $true)]
    [string]$OutputPath,
    [string]$ControlRoot = ""
)

$ErrorActionPreference = "Stop"

function New-ArMember {
    param(
        [string]$Name,
        [byte[]]$Content
    )

    $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = ('{0,-16}{1,-12}{2,-6}{3,-6}{4,-8}{5,-10}`n' -f $Name, $timestamp, 0, 0, '100644', $Content.Length)
    $headerBytes = [Text.Encoding]::ASCII.GetBytes($header)
    if ($headerBytes.Length -ne 60) {
        throw "Nieprawidłowy nagłówek ar dla $Name ($($headerBytes.Length) bajtów)."
    }

    $member = New-Object 'System.Collections.Generic.List[byte]'
    $member.AddRange($headerBytes)
    $member.AddRange($Content)
    if (($Content.Length % 2) -eq 1) {
        [void]$member.Add([byte]10)
    }
    return ,$member.ToArray()
}

$sourceRoot = [IO.Path]::GetFullPath($SourceRoot)
$outputPath = [IO.Path]::GetFullPath($OutputPath)
$controlRootSource = if ($ControlRoot) { [IO.Path]::GetFullPath($ControlRoot) } else { $sourceRoot }
$parent = Split-Path -Parent $outputPath
$workRoot = Join-Path $parent ".vendor-ipk-$([IO.Path]::GetFileNameWithoutExtension($outputPath))"
$dataRoot = Join-Path $workRoot "data"
$controlRoot = Join-Path $workRoot "control"
$dataTar = Join-Path $workRoot "data.tar.gz"
$controlTar = Join-Path $workRoot "control.tar.gz"

if (-not (Test-Path -LiteralPath (Join-Path $sourceRoot "usr"))) {
    throw "Brak katalogu usr w źródle: $sourceRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $controlRootSource "CONTROL\control"))) {
    throw "Brak pliku CONTROL/control w źródle: $controlRootSource"
}

if (Test-Path -LiteralPath $workRoot) {
    Remove-Item -LiteralPath $workRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $dataRoot, $controlRoot | Out-Null
Copy-Item -LiteralPath (Join-Path $sourceRoot "usr") -Destination $dataRoot -Recurse -Force
Copy-Item -LiteralPath (Join-Path $controlRootSource "CONTROL\control") -Destination (Join-Path $controlRoot "control") -Force

tar -czf $dataTar -C $dataRoot usr
tar -czf $controlTar -C $controlRoot control

$package = New-Object 'System.Collections.Generic.List[byte]'
$package.AddRange([Text.Encoding]::ASCII.GetBytes("!<arch>`n"))
$package.AddRange((New-ArMember "debian-binary" ([Text.Encoding]::ASCII.GetBytes("2.0`n"))))
$package.AddRange((New-ArMember "control.tar.gz" ([IO.File]::ReadAllBytes($controlTar))))
$package.AddRange((New-ArMember "data.tar.gz" ([IO.File]::ReadAllBytes($dataTar))))

[IO.File]::WriteAllBytes($outputPath, $package.ToArray())
Write-Output $outputPath
Get-FileHash -LiteralPath $outputPath -Algorithm SHA256 | ForEach-Object {
    Write-Output ("SHA256 " + $_.Hash)
}
