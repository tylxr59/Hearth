"""Create a local HA endpoint and a bounded, private USB commissioning bundle.

Server/CA private keys and manager credentials never leave the HA profile.
"""

import io
import ipaddress
import json
import os
import secrets
import shutil
import tempfile
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from backend.registry import Registry, private_json
from backend.validation import Invalid, endpoint, serial

FORMAT = "hearth-commissioning-v1"


def write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def key_bytes(key):
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def create_profile(directory, origin, ident):
    origin, ident = endpoint(origin), serial(ident)
    directory = Path(directory).absolute()
    if (
        directory.exists()
        or directory.is_symlink()
        or directory.parent.resolve() != directory.parent
    ):
        raise Invalid("fresh profile directory without symlinks required")
    address = ipaddress.ip_address(urlsplit(origin).hostname)
    temp = Path(tempfile.mkdtemp(prefix=".hearth-", dir=directory.parent))
    os.chmod(temp, 0o700)
    try:
        now = datetime.now(UTC)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        ca_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Hearth local authority")])
        ca = (
            x509.CertificateBuilder()
            .subject_name(ca_name)
            .issuer_name(ca_name)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1))
            .not_valid_after(now + timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )
        server = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Hearth local endpoint")])
            )
            .issuer_name(ca_name)
            .public_key(server_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(hours=1))
            .not_valid_after(now + timedelta(days=365))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address)]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .add_extension(
                x509.KeyUsage(True, False, True, False, False, False, False, False, False),
                critical=True,
            )
            .sign(ca_key, hashes.SHA256())
        )
        crl = (
            x509.CertificateRevocationListBuilder()
            .issuer_name(ca_name)
            .last_update(now - timedelta(hours=1))
            .next_update(now + timedelta(days=365))
            .sign(ca_key, hashes.SHA256())
        )
        pem = serialization.Encoding.PEM
        write(temp / "ca.pem", ca.public_bytes(pem))
        write(temp / "ca.key", key_bytes(ca_key))
        write(temp / "server.pem", server.public_bytes(pem))
        write(temp / "server.key", key_bytes(server_key))
        write(temp / "ca.crl", crl.public_bytes(pem))
        Registry.initialize(temp / "registry.json", temp / "admin.json")
        credential = secrets.token_hex(32)
        Registry(temp / "registry.json").register(
            ident, credential, {"modes": ["off", "heat", "cool"], "fan": True}
        )
        private_json(
            temp / "profile.json", {"format": "hearth-native-ha-profile-v1", "origin": origin}
        )
        device = {
            "format": FORMAT,
            "origin": origin,
            "serial": ident,
            "credential": credential,
            "supported_model": "Display-2.6",
            "supported_version": "5.9.4-5",
            "supported_partition": "primary",
            "certificate_expires": server.not_valid_after_utc.isoformat(),
        }
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in (
                ("commissioning.json", json.dumps(device, sort_keys=True).encode()),
                ("ca.pem", ca.public_bytes(pem)),
                ("ca.crl", crl.public_bytes(pem)),
            ):
                archive.writestr(name, data)
        write(temp / "commissioning.zip", stream.getvalue())
        # Directory rename is exclusive at the application boundary; never replace
        # an already prepared HA profile or rotate another user's credentials.
        if directory.exists():
            raise Invalid("profile appeared during preparation")
        os.rename(temp, directory)
        return {"origin": origin, "certificate_expires": device["certificate_expires"]}
    finally:
        if temp.exists():
            shutil.rmtree(temp)
