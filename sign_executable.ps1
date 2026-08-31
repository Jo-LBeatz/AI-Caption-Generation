# Powershell script to self-sign RegulaVitae_Captions.exe locally
$Cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject "CN=RegulaVitae Local Dev" -CertStoreLocation "Cert:\CurrentUser\My"

# Import to trusted root
$Store = Get-Item "Cert:\LocalMachine\Root"
$Store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
$Store.Add($Cert)
$Store.Close()

# Sign the exe
Set-AuthenticodeSignature -FilePath "dist\RegulaVitae_Captions\RegulaVitae_Captions.exe" -Certificate $Cert
Write-Host "[OK] Executable signed successfully with local certificate."
