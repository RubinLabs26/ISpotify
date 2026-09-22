# Windows release signing

Windows shows **Rubin Labs** as a verified publisher only when the executable has a trusted Authenticode signature from a code-signing certificate issued to Rubin Labs. The `CompanyName`, Inno Setup, and winget publisher fields are display metadata; they do not establish a trusted publisher by themselves.

Obtain a trusted code-signing certificate whose subject contains `CN=Rubin Labs` or `O=Rubin Labs` and which has the Code Signing extended key usage. The current GitHub Actions integration uses a password-protected PFX containing the certificate and private key. If the issuer provides only a hardware token or cloud-signing service, the workflow needs a provider-specific integration before it can sign releases.

Configure these **Actions** repository secrets in `RubinLabs26/ISpotify`:

- `WINDOWS_SIGNING_PFX_BASE64`: Base64 of the complete PFX file. On Windows, generate it locally with `[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\path\to\certificate.pfx'))`. Paste the result directly into the GitHub secret; do not commit or share it.
- `WINDOWS_SIGNING_PFX_PASSWORD`: The PFX password.

On Windows builds, `packaging/sign-windows.ps1` imports the certificate into the runner's temporary user store, checks its subject, validity period, private key, and Code Signing usage, then signs the portable EXE with SHA-256 and an RFC 3161 timestamp. Inno Setup uses the same certificate for the installer and uninstaller. The workflow verifies both published EXEs before calculating checksums or uploading assets. Missing credentials stop the Windows build before publication.

After credentials are configured and a signed release is built, update the winget installer SHA-256 to match the signed installer. Existing unsigned release assets should not be relabeled as signed.
