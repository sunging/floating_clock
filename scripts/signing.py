"""Optional release signing. Secrets never appear in command logging or artifacts."""

import base64
import os
import secrets
import shutil
import subprocess
from pathlib import Path


def quiet_run(arguments, label):
    result = subprocess.run(list(map(str, arguments)), check=False)
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit {result.returncode})")


def sign_windows(executable, work):
    encoded = os.environ.get("WINDOWS_CERTIFICATE_BASE64")
    if not encoded:
        return
    tool = shutil.which("signtool")
    if not tool:
        sdk = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Windows Kits/10/bin"
        matches = sorted(sdk.glob("*/x64/signtool.exe"))
        if not matches:
            raise RuntimeError("Windows signing was configured but signtool is unavailable")
        tool = matches[-1]
    certificate = work / "signing-certificate.pfx"
    certificate.write_bytes(base64.b64decode(encoded, validate=True))
    try:
        quiet_run(
            [
                tool,
                "sign",
                "/fd",
                "SHA256",
                "/td",
                "SHA256",
                "/tr",
                "https://timestamp.digicert.com",
                "/f",
                certificate,
                "/p",
                os.environ["WINDOWS_CERTIFICATE_PASSWORD"],
                executable,
            ],
            "Windows signing",
        )
        quiet_run([tool, "verify", "/pa", executable], "Windows signature verification")
    finally:
        certificate.unlink(missing_ok=True)


def sign_mac_app(application, work):
    encoded = os.environ.get("MACOS_CERTIFICATE_BASE64")
    if not encoded:
        quiet_run(["codesign", "--force", "--deep", "--sign", "-", application], "Ad-hoc signing")
        return
    certificate = work / "signing-certificate.p12"
    certificate.write_bytes(base64.b64decode(encoded, validate=True))
    keychain = work / "release-signing.keychain-db"
    password = secrets.token_hex(24)
    try:
        quiet_run(["security", "create-keychain", "-p", password, keychain], "Keychain creation")
        quiet_run(["security", "unlock-keychain", "-p", password, keychain], "Keychain unlock")
        quiet_run(
            [
                "security",
                "import",
                certificate,
                "-k",
                keychain,
                "-P",
                os.environ["MACOS_CERTIFICATE_PASSWORD"],
                "-T",
                "/usr/bin/codesign",
            ],
            "Certificate import",
        )
        quiet_run(
            [
                "security",
                "set-key-partition-list",
                "-S",
                "apple-tool:,apple:,codesign:",
                "-s",
                "-k",
                password,
                keychain,
            ],
            "Signing key permissions",
        )
        quiet_run(
            [
                "codesign",
                "--force",
                "--deep",
                "--options",
                "runtime",
                "--timestamp",
                "--keychain",
                keychain,
                "--sign",
                os.environ["MACOS_SIGN_IDENTITY"],
                application,
            ],
            "Developer ID signing",
        )
    finally:
        certificate.unlink(missing_ok=True)
        if keychain.exists():
            quiet_run(["security", "delete-keychain", keychain], "Temporary keychain removal")


def notarize_mac(dmg, work):
    encoded = os.environ.get("MACOS_NOTARY_KEY_BASE64")
    if not encoded:
        if os.environ.get("MACOS_CERTIFICATE_BASE64"):
            raise RuntimeError("Formal macOS signing requires notarization credentials")
        return
    if not os.environ.get("MACOS_CERTIFICATE_BASE64"):
        raise RuntimeError("Notarization requires a Developer ID signing certificate")
    key = work / "notary-key.p8"
    key.write_bytes(base64.b64decode(encoded, validate=True))
    key.chmod(0o600)
    try:
        quiet_run(
            [
                "xcrun",
                "notarytool",
                "submit",
                dmg,
                "--key",
                key,
                "--key-id",
                os.environ["MACOS_NOTARY_KEY_ID"],
                "--issuer",
                os.environ["MACOS_NOTARY_ISSUER"],
                "--wait",
                "--timeout",
                "30m",
            ],
            "macOS notarization",
        )
        quiet_run(["xcrun", "stapler", "staple", dmg], "Notarization stapling")
        quiet_run(["xcrun", "stapler", "validate", dmg], "Notarization verification")
    finally:
        key.unlink(missing_ok=True)
