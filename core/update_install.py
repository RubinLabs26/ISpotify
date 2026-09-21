"""Install a verified release asset using the host platform's supported path."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from core.paths import CACHE_DIR


def install_mode() -> str:
    if sys.platform == "win32":
        installed = (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs" / "ISpotify" / "ISpotify.exe"
        )
        if (
            getattr(sys, "frozen", False)
            and Path(sys.executable).resolve() != installed.resolve()
            and os.access(Path(sys.executable).parent, os.W_OK)
        ):
            return "windows-portable"
        return "windows-installer"
    if sys.platform.startswith("linux"):
        if Path("/var/lib/dpkg/info/ispotify.list").is_file() and shutil.which("pkexec"):
            return "debian-package"
        executable = Path(sys.executable)
        if (
            getattr(sys, "frozen", False)
            and executable.is_file()
            and os.access(executable.parent, os.W_OK)
            and "/opt/" not in str(executable)
        ):
            return "linux-portable"
    return "manual"


def install_windows(installer: Path) -> None:
    """Let a detached helper finish installation after this app exits.

    Inno Setup closes the running app before replacing its executable, so the
    restart question must be presented by the helper after Setup succeeds.
    """
    script = CACHE_DIR / "updates" / "install-windows.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        r'''param([string]$Installer, [int]$AppPid)
$ErrorActionPreference = 'Stop'
while (Get-Process -Id $AppPid -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 1
}
$process = Start-Process -FilePath $Installer -ArgumentList @(
    '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/CLOSEAPPLICATIONS'
) -Wait -PassThru -WindowStyle Hidden
Add-Type -AssemblyName System.Windows.Forms
if ($process.ExitCode -eq 0) {
    $answer = [System.Windows.Forms.MessageBox]::Show(
        'iSpotify was updated. Restart now to use the new version?',
        'iSpotify update',
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Information
    )
    if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) {
        $app = Join-Path $env:LOCALAPPDATA 'Programs\ISpotify\ISpotify.exe'
        if (Test-Path -LiteralPath $app) {
            Start-Process -FilePath $app -WindowStyle Hidden
        }
    }
} else {
    [System.Windows.Forms.MessageBox]::Show(
        "The iSpotify installer exited with code $($process.ExitCode).",
        'iSpotify update',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}
''',
        encoding="utf-8",
    )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [
            "powershell.exe", "-NoProfile", "-Sta", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-Installer", str(installer),
            "-AppPid", str(os.getpid()),
        ],
        close_fds=True,
        creationflags=creationflags,
    )


def install_windows_portable(download: Path) -> None:
    """Replace a portable executable after it exits, then offer restart."""
    script = CACHE_DIR / "updates" / "install-portable.ps1"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        r'''param([string]$Download, [string]$Target, [int]$AppPid)
$ErrorActionPreference = 'Stop'
while (Get-Process -Id $AppPid -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 1
}
Add-Type -AssemblyName System.Windows.Forms
try {
    Move-Item -LiteralPath $Download -Destination $Target -Force
    $answer = [System.Windows.Forms.MessageBox]::Show(
        'iSpotify was updated. Restart now to use the new version?',
        'iSpotify update',
        [System.Windows.Forms.MessageBoxButtons]::YesNo,
        [System.Windows.Forms.MessageBoxIcon]::Information
    )
    if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) {
        Start-Process -FilePath $Target -WindowStyle Hidden
    }
} catch {
    [System.Windows.Forms.MessageBox]::Show(
        "Could not install the iSpotify update: $_",
        'iSpotify update',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}
''',
        encoding="utf-8",
    )
    subprocess.Popen(
        [
            "powershell.exe", "-NoProfile", "-Sta", "-ExecutionPolicy", "Bypass",
            "-File", str(script), "-Download", str(download),
            "-Target", sys.executable, "-AppPid", str(os.getpid()),
        ],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def install_linux_portable(download: Path) -> None:
    target = Path(sys.executable)
    staged = target.with_name(target.name + ".update")
    try:
        shutil.copy2(download, staged)
        staged.chmod(0o755)
        os.replace(staged, target)
    finally:
        staged.unlink(missing_ok=True)
