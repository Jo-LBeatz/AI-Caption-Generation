# Powershell script to self-sign Verbum.exe and installer locally
$Cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=Verbum Catholic AI" -CertStoreLocation "Cert:\CurrentUser\My"

# Import to trusted root
try {
    $Store = Get-Item "Cert:\LocalMachine\Root"
    $Store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
    $Store.Add($Cert)
    $Store.Close()
} catch {
    Write-Host "[INFO] Root store requires admin privileges, signing with current user cert."
}

# Sign the binaries if they exist
if (Test-Path "dist\Verbum\Verbum.exe") {
    Set-AuthenticodeSignature -FilePath "dist\Verbum\Verbum.exe" -Certificate $Cert
    Write-Host "[OK] dist\Verbum\Verbum.exe signed successfully."
}

if (Test-Path "installer_output\Verbum_Setup_v2.0.0.exe") {
    Set-AuthenticodeSignature -FilePath "installer_output\Verbum_Setup_v2.0.0.exe" -Certificate $Cert
    Write-Host "[OK] installer_output\Verbum_Setup_v2.0.0.exe signed successfully."
}
