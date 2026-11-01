"""Load a locally prepared profile without placing secrets in config entries."""

import ipaddress
import os
import ssl
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm

from ._backend.registry import Registry
from ._backend.validation import Invalid, endpoint, loads
from .const import PROFILE_FILES, PROFILE_FORMAT

PROFILE_ERRORS = (
    OSError,
    ValueError,
    InvalidSignature,
    UnsupportedAlgorithm,
    x509.ExtensionNotFound,
)


def private_read(path: Path, maximum: int) -> bytes:
    """No symlink, shared inode, public permissions, special file or oversized read."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        meta = os.fstat(fd)
        if (
            not stat.S_ISREG(meta.st_mode)
            or meta.st_mode & 0o077
            or meta.st_nlink != 1
            or meta.st_size > maximum
        ):
            raise Invalid("private bounded profile file required")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(maximum + 1)
        if len(data) > maximum:
            raise Invalid("profile file exceeds limit")
        return data
    finally:
        os.close(fd)


@dataclass
class PreparedProfile:
    origin: str
    registry: Registry
    context: ssl.SSLContext


def load_profile(directory: Path) -> PreparedProfile:
    directory = Path(directory).absolute()
    if directory.resolve() != directory or directory.stat().st_mode & 0o077:
        raise Invalid("private profile directory required")
    blobs = {name: private_read(directory / name, 1024 * 1024) for name in PROFILE_FILES}
    data = loads(blobs["profile.json"])
    if (
        not isinstance(data, dict)
        or set(data) != {"format", "origin"}
        or data["format"] != PROFILE_FORMAT
    ):
        raise Invalid("prepared native Home Assistant profile required")
    origin = endpoint(data["origin"])
    certificate = x509.load_pem_x509_certificate(blobs["server.pem"])
    authority = x509.load_pem_x509_certificate(blobs["ca.pem"])
    certificate.verify_directly_issued_by(authority)
    now = datetime.now(UTC)
    if not certificate.not_valid_before_utc <= now <= certificate.not_valid_after_utc:
        raise Invalid("server certificate is outside its validity period")
    address = ipaddress.ip_address(urlsplit(origin).hostname)
    sans = certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    if address not in sans.get_values_for_type(x509.IPAddress):
        raise Invalid("server certificate does not cover configured address")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(directory / "server.pem", directory / "server.key")
    registry = Registry(directory / "registry.json")
    if not registry.data["devices"]:
        raise Invalid("profile has no enrolled thermostat")
    return PreparedProfile(origin, registry, context)
