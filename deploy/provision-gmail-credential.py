#!/usr/bin/env python3
"""Run as root on Linux; reads the app password only from a hidden terminal prompt."""
import getpass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


def main():
    if os.name != "posix" or os.geteuid() != 0:
        raise SystemExit("Execute como root na VM Linux.")
    if not sys.stdin.isatty():
        raise SystemExit("Use um terminal interativo para a entrada oculta da credencial.")
    version = subprocess.run(["systemctl", "--version"], capture_output=True, check=True, text=True)
    match = re.search(r"systemd (\d+)", version.stdout)
    encrypted = bool(match and int(match.group(1)) >= 250 and shutil.which("systemd-creds"))
    password = getpass.getpass("Senha de aplicativo Gmail (entrada oculta): ").replace(" ", "")
    if not re.fullmatch(r"[A-Za-z]{16}", password):
        raise SystemExit("Informe uma senha de aplicativo Gmail de 16 letras.")
    directory = Path("/etc/credstore.encrypted" if encrypted else "/etc/sar/credentials")
    if directory.is_symlink():
        raise SystemExit("Diretório de credenciais não pode ser um link.")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory.chmod(0o700)
    os.chown(directory, 0, 0)
    name = "sar-gmail-app-password" if encrypted else "gmail-app-password"
    if encrypted:
        process = subprocess.run(
            ["systemd-creds", "encrypt", "--name=gmail-app-password", "-", "-"],
            input=password.encode("utf-8"), capture_output=True,
        )
        if process.returncode:
            raise SystemExit("Falha ao cifrar credencial; nenhum segredo foi instalado.")
        content = process.stdout
    else:
        content = password.encode("utf-8")
    password = None
    fd, temp_path = tempfile.mkstemp(prefix=".gmail-", dir=directory)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, directory / name)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    directive = "LoadCredentialEncrypted" if encrypted else "LoadCredential"
    print(f"Credencial instalada. Use na unidade worker: {directive}=gmail-app-password:{directory / name}")
    if not encrypted:
        print("Arquivo protegido por permissões root; conteúdo não cifrado em repouso (systemd <250).")


if __name__ == "__main__":
    main()
