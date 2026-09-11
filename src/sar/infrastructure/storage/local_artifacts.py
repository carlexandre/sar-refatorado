import hashlib
import os
from pathlib import Path
import re
import uuid
from sar.domain.errors import NotFound, ValidationError
from sar.domain.models import Artifact
from sar.security.validation import filename


class LocalArtifacts:
    def __init__(self, root: Path):
        self.root = root.resolve()

    def _path(self, identifier: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", identifier):
            raise ValidationError("Identificador de documento inválido.")
        path = self.root / f"{identifier}.pdf"
        if path.is_symlink() or not path.resolve().is_relative_to(self.root):
            raise ValidationError("Caminho de documento inválido.")
        return path

    def save(self, data: bytes, name: str) -> Artifact:
        if not isinstance(data, bytes) or not data.startswith(b"%PDF-"):
            raise ValidationError("Documento PDF inválido.")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        identifier = uuid.uuid4().hex
        target = self._path(identifier)
        temporary = self.root / f".{identifier}.tmp"
        try:
            with open(temporary, "xb") as stream:
                if os.name == "posix":
                    os.chmod(temporary, 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return Artifact(identifier, filename(name), hashlib.sha256(data).hexdigest(), len(data))

    def read(self, identifier: str) -> bytes:
        path = self._path(identifier)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        try:
            with os.fdopen(os.open(path, flags), "rb") as stream:
                return stream.read()
        except FileNotFoundError:
            raise NotFound("Documento não encontrado no armazenamento.") from None

    def remove_unregistered(self, identifier: str) -> None:
        self._path(identifier).unlink(missing_ok=True)
