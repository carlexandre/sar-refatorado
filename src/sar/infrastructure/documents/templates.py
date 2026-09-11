import json
from pathlib import Path
from sar.domain.errors import ConfigurationError

ROOT = Path(__file__).parents[2] / "resources"


def asset(name: str) -> str:
    if name not in {
        "gigafor-logo.png",
        "pop-ce-logo-preto.png",
        "pop-ce-logo-branca.png",
        "rnp-logo-preto.png",
    }:
        raise ConfigurationError("Asset de template inválido.")
    return str(ROOT / "assets" / "logo" / name)


def load_template(version="legacy_v1") -> dict:
    if version != "legacy_v1":
        raise ConfigurationError("Versão de template não suportada.")
    data = json.loads((ROOT / "templates" / version / "template.json").read_text(encoding="utf-8"))
    if data.get("version") != version:
        raise ConfigurationError("Template inválido.")
    for section in ("texts", "issuer"):
        if not isinstance(data.get(section), dict) or any(
            not isinstance(v, str) for v in data[section].values()
        ):
            raise ConfigurationError("Conteúdo de template inválido.")
    for color in data["colors"].values():
        if len(color) != 3 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in color):
            raise ConfigurationError("Cor de template inválida.")
    return data
