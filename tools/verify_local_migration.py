"""Verify a real local legacy copy without sending data to any external service."""

import hashlib
import json
from pathlib import Path
import tempfile
from sar.infrastructure.persistence.migration import import_legacy

root = Path(__file__).resolve().parents[1]
source = root.parent / "SAR - Sistema de Automatização de Relatórios"
tracked_inputs = [*source.glob("*.py"), source / "relatorios_popce.db", *source.glob("pdfs_gerados/*.pdf")]
before = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked_inputs}
parent = root / "tmp"
parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=parent) as temporary:
    target = Path(temporary)
    result = import_legacy(
        source / "relatorios_popce.db", target / "sar.db", source / "pdfs_gerados", target / "artifacts"
    )
after = {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked_inputs}
if before != after:
    raise RuntimeError("Legacy input changed during verification")
result["legacy_unchanged"] = True
result["files_verified"] = len(before)
output = root / "docs" / "migration-verification.json"
output.parent.mkdir(exist_ok=True)
output.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
