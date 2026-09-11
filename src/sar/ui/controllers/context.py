from dataclasses import dataclass


@dataclass
class Controller:
    """Binds trusted identity; views never supply identity or permissions."""

    app: object
    identity: object | None = None
    pages: dict | None = None

    def call(self, service, method, *args, **kwargs):
        identity = self.identity if self.identity is not None else self.app.identities.current()
        return getattr(getattr(self.app, service), method)(identity, *args, **kwargs)
