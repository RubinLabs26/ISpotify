param(
    [string]$PortablePath = "dist/windows/ISpotify-windows-x86_64.exe",
    [string]$InstallerScript = "packaging/windows-installer.iss"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $env:WINDOWS_SIGNING_PFX_BASE64 -or -not $env:WINDOWS_SIGNING_PFX_PASSWORD) {
    throw "A Rubin Labs code-signing PFX and password are required to publish Windows builds."
}

$sdkBin = Join-Path ${env:ProgramFiles(x86)} "Windows Kits/10/bin"
$signTool = Get-ChildItem -LiteralPath $sdkBin -Filter signtool.exe -Recurse -File |
    Where-Object { $_.FullName -match '[\\/]x64[\\/]signtool\.exe$' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if (-not $signTool) {
    throw "Windows SDK SignTool was not found."
}

$pfxPath = Join-Path $env:RUNNER_TEMP "rubin-labs-signing.pfx"
$certificate = $null
try {
    [IO.File]::WriteAllBytes(
        $pfxPath,
        [Convert]::FromBase64String($env:WINDOWS_SIGNING_PFX_BASE64)
    )
    $password = ConvertTo-SecureString $env:WINDOWS_SIGNING_PFX_PASSWORD -AsPlainText -Force
    $imported = Import-PfxCertificate -FilePath $pfxPath -Password $password -CertStoreLocation Cert:\CurrentUser\My
    $certificate = @($imported) | Where-Object HasPrivateKey | Select-Object -First 1
    if (-not $certificate -or -not $certificate.HasPrivateKey) {
        throw "The signing certificate has no private key."
    }
    if ($certificate.Subject -notmatch '(?:^|,\s*)(?:CN|O)=Rubin Labs(?:,|$)') {
        throw "The signing certificate must identify Rubin Labs as its subject or organization."
    }
    if ($certificate.NotBefore -gt (Get-Date) -or $certificate.NotAfter -lt (Get-Date)) {
        throw "The Rubin Labs signing certificate is outside its validity period."
    }
    $codeSigningEku = "1.3.6.1.5.5.7.3.3"
    $eku = $certificate.Extensions |
        Where-Object { $_.Oid.Value -eq "2.5.29.37" } |
        Select-Object -First 1
    if (-not $eku -or $codeSigningEku -notin $eku.EnhancedKeyUsages.Value) {
        throw "The Rubin Labs certificate is not valid for code signing."
    }

    $thumbprint = $certificate.Thumbprint
    $timestamp = "http://timestamp.digicert.com"
    & $signTool.FullName sign /sha1 $thumbprint /s My /fd SHA256 /tr $timestamp /td SHA256 /d "iSpotify" $PortablePath
    if ($LASTEXITCODE -ne 0) { throw "Signing the portable executable failed." }

    $innoSignTool = 'RubinSign=$q' + $signTool.FullName +
        '$q sign /sha1 ' + $thumbprint +
        ' /s My /fd SHA256 /tr ' + $timestamp +
        ' /td SHA256 /d $qiSpotify$q $f'
    & iscc /DSIGN_WINDOWS=1 "-s$innoSignTool" $InstallerScript
    if ($LASTEXITCODE -ne 0) { throw "Building or signing the installer failed." }

    foreach ($file in @($PortablePath, "dist/installer/ISpotify-Setup-x86_64.exe")) {
        & $signTool.FullName verify /pa /tw $file
        if ($LASTEXITCODE -ne 0) { throw "Authenticode verification failed for $file." }
        $signature = Get-AuthenticodeSignature -LiteralPath $file
        if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Thumbprint -ne $thumbprint) {
            throw "The signer of $file does not match the Rubin Labs certificate."
        }
    }
}
finally {
    if ($certificate) {
        Remove-Item -LiteralPath "Cert:\CurrentUser\My\$($certificate.Thumbprint)" -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $pfxPath -ErrorAction SilentlyContinue
}
