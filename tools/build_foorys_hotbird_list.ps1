param(
    [string]$SourceArchive = "channel-lists/bzyk83-2026.08.23/bzyk83-hb.zip",
    [string]$OutputArchive = "channel-lists/foorys-hotbird-2026.08.23/foorys-hotbird-13e.zip"
)

$ErrorActionPreference = "Stop"

function Write-Utf8File {
    param(
        [string]$Path,
        [string]$Content
    )

    [IO.File]::WriteAllText($Path, $Content, [Text.UTF8Encoding]::new($false))
}

function Copy-Bouquet {
    param(
        [string]$SourceRoot,
        [string]$DestinationRoot,
        [string]$SourceName,
        [string]$DestinationName,
        [string]$DisplayName
    )

    $content = [IO.File]::ReadAllText((Join-Path $SourceRoot $SourceName))
    $content = [regex]::Replace($content, '(?m)^#NAME.*$', "#NAME $DisplayName", 1)
    if (-not $content.StartsWith("#NAME ")) {
        $content = "#NAME $DisplayName`n$content"
    }
    $content = $content.TrimEnd("`r", "`n") + "`n"
    Write-Utf8File -Path (Join-Path $DestinationRoot $DestinationName) -Content $content
}

$sourcePath = [IO.Path]::GetFullPath($SourceArchive)
$outputPath = [IO.Path]::GetFullPath($OutputArchive)
$outputDirectory = Split-Path -Parent $outputPath
if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Nie znaleziono archiwum źródłowego: $sourcePath"
}

$workRoot = Join-Path ([IO.Path]::GetTempPath()) ("foorys-hotbird-" + [guid]::NewGuid().ToString("N"))
$sourceRoot = Join-Path $workRoot "source"
$listRoot = Join-Path $workRoot "list"

try {
    New-Item -ItemType Directory -Force -Path $sourceRoot, $listRoot, $outputDirectory | Out-Null
    Expand-Archive -LiteralPath $sourcePath -DestinationPath $sourceRoot -Force

    foreach ($name in @("lamedb", "satellites.xml")) {
        $source = Join-Path $sourceRoot $name
        if (-not (Test-Path -LiteralPath $source)) {
            throw "Archiwum źródłowe nie zawiera wymaganego pliku: $name"
        }
        Copy-Item -LiteralPath $source -Destination (Join-Path $listRoot $name) -Force
    }

    $lamedbPath = Join-Path $listRoot "lamedb"
    $lamedb = [IO.File]::ReadAllText($lamedbPath)
    $lamedb = [regex]::Replace($lamedb, '(?im)^p:bzyk83\s*$', 'p:Foorys')
    Write-Utf8File -Path $lamedbPath -Content $lamedb

    Copy-Bouquet -SourceRoot $sourceRoot -DestinationRoot $listRoot -SourceName "userbouquet.polskie.tv" -DestinationName "userbouquet.foorys.polskie.tv" -DisplayName "Foorys | Polskie"
    Copy-Bouquet -SourceRoot $sourceRoot -DestinationRoot $listRoot -SourceName "userbouquet.fta13e.tv" -DestinationName "userbouquet.foorys.fta.tv" -DisplayName "Foorys | FTA Hotbird 13E"
    Copy-Bouquet -SourceRoot $sourceRoot -DestinationRoot $listRoot -SourceName "userbouquet.dbe14.tv" -DestinationName "userbouquet.foorys.xxx.tv" -DisplayName "Foorys | XXX"

    $bouquets = @(
        "#NAME Foorys | Hotbird 13E"
        '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.foorys.polskie.tv" ORDER BY bouquet'
        '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.foorys.fta.tv" ORDER BY bouquet'
        '#SERVICE 1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "userbouquet.foorys.xxx.tv" ORDER BY bouquet'
    ) -join "`n"
    Write-Utf8File -Path (Join-Path $listRoot "bouquets.tv") -Content ($bouquets + "`n")

    if (Test-Path -LiteralPath $outputPath) {
        Remove-Item -LiteralPath $outputPath -Force
    }
    Compress-Archive -Path (Join-Path $listRoot "*") -DestinationPath $outputPath -CompressionLevel Optimal
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
