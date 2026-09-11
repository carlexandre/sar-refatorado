"""Freeze the resolved production graph separately from local verification tools."""

import importlib.metadata as metadata
from pathlib import Path
from packaging.requirements import Requirement
from packaging.markers import default_environment
from packaging.utils import canonicalize_name

root = Path(__file__).resolve().parents[1]


def graph(names):
    result = {}
    pending = list(names)
    while pending:
        name = canonicalize_name(pending.pop())
        if name in result:
            continue
        dist = metadata.distribution(name)
        result[name] = dist.version
        for raw in dist.requires or []:
            requirement = Requirement(raw)
            environments = [
                default_environment(),
                {
                    **default_environment(),
                    "sys_platform": "linux",
                    "os_name": "posix",
                    "platform_system": "Linux",
                },
            ]
            if not requirement.marker or any(
                requirement.marker.evaluate({**env, "extra": ""}) for env in environments
            ):
                pending.append(requirement.name)
    return result


production = graph([
    "streamlit", "fpdf2", "pandas", "matplotlib", "pyzabbix", "requests", "tzdata", "argon2-cffi"
])
development = graph(["pytest", "pypdf", "pymupdf", "ruff", "bandit", "pip-audit", "setuptools", "wheel"])
(root / "requirements.lock").write_text(
    "# Resolved on Python 3.12; install before the package.\n"
    + "\n".join(f"{name}=={version}" for name, version in sorted(production.items()))
    + "\n",
    encoding="utf-8",
)
(root / "requirements-dev.lock").write_text(
    "-r requirements.lock\n"
    + "\n".join(
        f"{name}=={version}" for name, version in sorted(development.items()) if name not in production
    )
    + "\n",
    encoding="utf-8",
)
