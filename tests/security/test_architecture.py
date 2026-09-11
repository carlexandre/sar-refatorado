import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "src" / "sar"


def imports(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (n.name for n in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


def test_domain_is_independent():
    for path in (ROOT / "domain").glob("*.py"):
        assert not any(
            name.startswith(
                (
                    "streamlit",
                    "sqlite3",
                    "requests",
                    "pandas",
                    "fpdf",
                    "sar.infrastructure",
                    "sar.application",
                )
            )
            for name in imports(path)
        ), path


def test_views_have_no_infrastructure():
    for path in (ROOT / "ui" / "views").glob("*.py"):
        assert not any(
            name.startswith(("sqlite3", "smtplib", "requests", "subprocess", "sar.infrastructure"))
            for name in imports(path)
        ), path
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert not any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "open"
            for n in ast.walk(tree)
        ), path


def test_workers_do_not_import_streamlit():
    for directory in ("workers", "application"):
        for path in (ROOT / directory).rglob("*.py"):
            assert not any(name.startswith("streamlit") for name in imports(path)), path
