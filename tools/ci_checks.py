"""Portable CI entrypoint. No integration endpoints or credentials are needed."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
commands = [
    [sys.executable, "-m", "ruff", "check", "src", "tests", "tools", "app.py"],
    [sys.executable, "-m", "pytest", "-q", "--disable-warnings"],
    [sys.executable, "-m", "bandit", "-r", "src", "-ll", "-q"],
    [sys.executable, "tools/security_scan.py"],
]
if "--audit" in sys.argv:
    commands.append(
        [sys.executable, "-m", "pip_audit", "-r", "requirements.lock", "--no-deps", "--disable-pip"]
    )
for command in commands:
    result = subprocess.run(command, cwd=root, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)
