param(
    [string]$ManifestPath = "manifest.json",
    [string]$PiconDirectory = "picons"
)

$ErrorActionPreference = "Stop"

$sourcePage = "https://picon.cz/download-picons/picon-transparent-220x132/"
$userAgent = "E2-Foorys picon mirror updater"
$headers = @{
    "User-Agent" = $userAgent
    "Referer" = $sourcePage
}

$sources = @(
    @{ Id = 1105; Satellite = "13.0E"; FileName = "picontransparent-220x132-13.0E.7z" },
    @{ Id = 1125; Satellite = "19.2E"; FileName = "picontransparent-220x132-19.2E.7z" }
)

function Get-BuildVersion {
    param([string]$Html, [int]$DownloadId)

    $pattern = 'title="Build\s+(?<build>\d{6})"\s+href="https://picon\.cz/download/' + $DownloadId + '/"'
    $match = [regex]::Match($Html, $pattern, [Text.RegularExpressions.RegexOptions]::IgnoreCase)
    if (-not $match.Success) {
        throw "Nie znaleziono daty Build dla pobrania $DownloadId na stronie źródłowej."
    }
    $build = $match.Groups["build"].Value
    return "20$($build.Substring(0, 2)).$($build.Substring(2, 2)).$($build.Substring(4, 2))"
}

function Assert-7Zip {
    param([string]$Path)

    $bytes = [IO.File]::ReadAllBytes($Path)
    $magic = [byte[]](0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C)
    if ($bytes.Length -lt $magic.Length) {
        throw "Pobrany picon jest pusty lub zbyt krótki: $Path"
    }
    for ($index = 0; $index -lt $magic.Length; $index++) {
        if ($bytes[$index] -ne $magic[$index]) {
            throw "Źródło nie zwróciło archiwum 7z: $Path"
        }
    }
}

$manifestPath = [IO.Path]::GetFullPath($ManifestPath)
$piconDirectory = [IO.Path]::GetFullPath($PiconDirectory)
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw "Brak manifestu: $manifestPath"
}
New-Item -ItemType Directory -Force -Path $piconDirectory | Out-Null

$page = Invoke-WebRequest -Uri $sourcePage -Headers $headers -UseBasicParsing
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($null -eq $manifest.picons) {
    $manifest | Add-Member -MemberType NoteProperty -Name picons -Value @()
}

$updated = @()
$changed = $false
foreach ($source in $sources) {
    $version = Get-BuildVersion -Html $page.Content -DownloadId $source.Id
    $downloadUrl = "https://picon.cz/download/$($source.Id)/"
    $destination = Join-Path $piconDirectory $source.FileName
    $temporary = "$destination.part"
    $entryId = "chocholousek-220x132-$($source.Satellite.ToLowerInvariant())"
    $entry = @($manifest.picons) | Where-Object { $_.id -eq $entryId } | Select-Object -First 1
    $previousHash = if ($entry) { [string]$entry.sha256 } else { "" }
    $previousVersion = if ($entry) { [string]$entry.version } else { "" }
    $previousFileHash = if (Test-Path -LiteralPath $destination) {
        (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    } else { "" }

    Write-Output "Pobieram picony $($source.Satellite) Build $version..."
    if (Test-Path -LiteralPath $temporary) {
        Remove-Item -LiteralPath $temporary -Force
    }
    Invoke-WebRequest -Uri $downloadUrl -Headers $headers -OutFile $temporary -UseBasicParsing
    Assert-7Zip -Path $temporary
    $hash = (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($hash -ne $previousFileHash) {
        Move-Item -LiteralPath $temporary -Destination $destination -Force
        $changed = $true
    } else {
        Remove-Item -LiteralPath $temporary -Force
    }

    if ($null -eq $entry) {
        $entry = [pscustomobject]@{}
        $manifest.picons = @($manifest.picons) + $entry
    }
    $entry | Add-Member -Force -MemberType NoteProperty -Name id -Value $entryId
    $entry | Add-Member -Force -MemberType NoteProperty -Name name -Value "Chocholousek Picons 220x132 $($source.Satellite)"
    $entry | Add-Member -Force -MemberType NoteProperty -Name description -Value "Transparentne picony 220x132 dla $($source.Satellite), mirror centralny E2-Foorys; aktualizacja inkrementalna."
    $entry | Add-Member -Force -MemberType NoteProperty -Name version -Value $version
    $entry | Add-Member -Force -MemberType NoteProperty -Name archive_type -Value "7z"
    $entry | Add-Member -Force -MemberType NoteProperty -Name satellites -Value $source.Satellite
    $entry | Add-Member -Force -MemberType NoteProperty -Name url -Value "picons/$($source.FileName)"
    $entry | Add-Member -Force -MemberType NoteProperty -Name sha256 -Value $hash
    $entry | Add-Member -Force -MemberType NoteProperty -Name source_url -Value $sourcePage
    if ($previousHash -ne $hash -or $previousVersion -ne $version) {
        $changed = $true
    }
    $updated += "$($source.FileName) $hash"
}

$message = if ($changed) { "Zaktualizowano manifest i mirror piconów:" } else { "Mirror piconów jest aktualny:" }
if ($changed) {
    $manifest.generated_at = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $json = $manifest | ConvertTo-Json -Depth 10
    [IO.File]::WriteAllText($manifestPath, $json + "`n", [Text.UTF8Encoding]::new($false))
}
Write-Output $message
$updated | ForEach-Object { Write-Output $_ }
