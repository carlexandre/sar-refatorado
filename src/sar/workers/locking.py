from contextlib import contextmanager
import os
from sar.domain.errors import ValidationError


@contextmanager
def exclusive_lock(path, wait=False):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    stream = open(path, "a+b")
    try:
        if os.name == "nt":
            import msvcrt

            # Inspecting the locked byte itself raises PermissionError on Windows.
            # File length can be checked without touching that locked region.
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValidationError(
                    "Outro worker está em execução. Tente novamente após a conclusão."
                ) from None
        else:
            import fcntl

            try:
                fcntl.flock(stream, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
            except BlockingIOError:
                raise ValidationError(
                    "Outro worker está em execução. Tente novamente após a conclusão."
                ) from None
        yield
    finally:
        # Closing releases OS locks even on exceptions or process termination.
        stream.close()
