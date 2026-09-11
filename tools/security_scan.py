"""Small deterministic guardrail, not a substitute for corporate secret scanning."""

import ast
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
problems = []
for path in (root / "src").rglob("*.py"):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if (
                isinstance(node.value.value, str)
                and node.value.value
                and any(re.search(r"password|senha|api[_]?token|secret[_]?key", name, re.I) for name in names)
            ):
                problems.append((path.name, node.lineno, "embedded credential"))
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (
                    kw.arg in {"shell", "unsafe_allow_html"}
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is True
                ):
                    problems.append((path.name, node.lineno, "unsafe execution/rendering"))
                if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                    problems.append((path.name, node.lineno, "TLS disabled"))
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and node.value.value is False
        ):
            if any(
                isinstance(t, ast.Attribute) and t.attr in {"verify", "check_hostname"} for t in node.targets
            ):
                problems.append((path.name, node.lineno, "TLS disabled"))
    if "BEGIN PRIVATE KEY" in source or "BEGIN RSA PRIVATE KEY" in source:
        problems.append((path.name, 0, "private key material"))
for problem in problems:
    print("%s:%s %s" % problem)
print(f"Source guardrails: {len(problems)} findings")
raise SystemExit(bool(problems))
