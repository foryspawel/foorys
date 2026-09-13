param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$PluginRoot = "plugin",
    [string]$OutputPath = ""
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

$pluginRoot = [IO.Path]::GetFullPath($PluginRoot)
if (-not (Test-Path -LiteralPath (Join-Path $pluginRoot "usr"))) {
    throw "Brak katalogu usr w źródle pluginu: $pluginRoot"
}

if (-not $OutputPath) {
    $OutputPath = Join-Path "releases" "enigma2-plugin-extensions-e2foorys_${Version}_all.ipk"
}
$outputPath = [IO.Path]::GetFullPath($OutputPath)
$parent = Split-Path -Parent $outputPath
$workRoot = Join-Path $parent ".foorys-ipk-$([IO.Path]::GetFileNameWithoutExtension($outputPath))"
$dataRoot = Join-Path $workRoot "data"
$controlRoot = Join-Path $workRoot "control"
$dataTar = Join-Path $workRoot "data.tar.gz"
$controlTar = Join-Path $workRoot "control.tar.gz"

try {
    if (Test-Path -LiteralPath $workRoot) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $dataRoot, $controlRoot, $parent | Out-Null
    Copy-Item -LiteralPath (Join-Path $pluginRoot "usr") -Destination $dataRoot -Recurse -Force

    Get-ChildItem -LiteralPath $dataRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force
    Get-ChildItem -LiteralPath $dataRoot -Recurse -File -Include "*.pyc", "*.pyo" -ErrorAction SilentlyContinue |
        Remove-Item -Force

    $controlText = @(
        "Package: enigma2-plugin-extensions-e2foorys"
        "Version: $Version"
        "Architecture: all"
        "Maintainer: Foorys"
        "Description: E2-Foorys - zarządzanie listami kanałów, pluginami i softcamami"
    ) -join "`n"
    [IO.File]::WriteAllText((Join-Path $controlRoot "control"), $controlText + "`n", [Text.UTF8Encoding]::new($false))

    tar -czf $dataTar -C $dataRoot usr
    if ($LASTEXITCODE -ne 0) { throw "Nie udało się zbudować data.tar.gz." }
    tar -czf $controlTar -C $controlRoot control
    if ($LASTEXITCODE -ne 0) { throw "Nie udało się zbudować control.tar.gz." }

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
}
finally {
    if (Test-Path -LiteralPath $workRoot) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
