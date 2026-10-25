"""Local credential registry. No shared defaults or serial-derived secrets."""

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from pathlib import Path

from backend.validation import Invalid, capabilities, serial


def digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def token_valid(token):
    return isinstance(token, str) and re.fullmatch(r"[0-9a-f]{64}", token) is not None


def private_json(path, data, *, replace=False):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(data, stream, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(tmp, path)
        else:
            os.link(tmp, path)  # exclusive creation, including against symlinks
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Registry:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink() or not self.path.is_file() or self.path.stat().st_mode & 0o077:
            raise Invalid("registry must be a private regular file")
        self.data = json.loads(self.path.read_text())

    @classmethod
    def initialize(cls, path, admin_file):
        token = secrets.token_hex(32)
        private_json(admin_file, {"token": token})
        private_json(path, {"admin": digest(token), "devices": {}})
        return cls(path)

    def rotate_admin(self, output):
        token = secrets.token_hex(32)
        private_json(output, {"token": token})
        self.data["admin"] = digest(token)
        self.save()

    def admin(self, token):
        return token_valid(token) and hmac.compare_digest(digest(token), self.data["admin"])

    def authenticate(self, ident, token):
        record = self.data["devices"].get(ident)
        expected = record["hash"] if record else "0" * 64
        match = token_valid(token) and hmac.compare_digest(digest(token), expected)
        return bool(record and match)

    def register(self, ident, token, caps, *, rotate=False):
        serial(ident)
        capabilities(caps)
        if not token_valid(token):
            raise Invalid("credential must contain 256 random bits encoded as hex")
        if ident in self.data["devices"] and not rotate:
            raise Invalid("already registered; use explicit rotation")
        new_hash = digest(token)
        if hmac.compare_digest(new_hash, self.data["admin"]) or any(
            other != ident and hmac.compare_digest(record["hash"], new_hash)
            for other, record in self.data["devices"].items()
        ):
            raise Invalid("credentials must be unique and role-specific")
        self.data["devices"][ident] = {"hash": digest(token), "capabilities": caps}
        self.save()

    def revoke(self, ident):
        self.data["devices"].pop(ident, None)
        self.save()

    def save(self):
        private_json(self.path, self.data, replace=True)
