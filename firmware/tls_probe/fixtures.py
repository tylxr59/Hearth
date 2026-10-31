"""Generate synthetic TLS fixtures privately; no device credentials are accepted."""

import argparse
import hashlib
import json
import re

# Fixed OpenSSL argv, synthetic data only, no shell or device access.
import subprocess  # nosec B404

from tools.elf_review import private_path

EPOCH = 1893456000
CASES = (
    "valid",
    "wrong_ca",
    "wrong_host",
    "expired_cert",
    "future_cert",
    "missing_issuer_crl",
    "expired_crl",
    "future_crl",
    "revoked_cert",
)
TARGET_FILES = {
    "ca.pem",
    "other-ca.pem",
    "server.key",
    "valid.pem",
    "wrong-host.pem",
    "expired.pem",
    "future.pem",
    "good.crl",
    "other.crl",
    "expired.crl",
    "future.crl",
    "revoked.crl",
}


def openssl(*arguments, check=True):
    return subprocess.run(  # nosec B607
        ["openssl", *map(str, arguments)],
        capture_output=True,
        check=check,
        timeout=30,
        shell=False,  # nosec B603
    )


def generate(output):
    output = private_path(output)
    if not re.fullmatch(r"/[A-Za-z0-9_./-]+", str(output)):
        raise ValueError("simple private build path required by OpenSSL config")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for label in ("ca", "other-ca"):
        openssl(
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-noenc",
            "-days",
            "3650",
            "-keyout",
            output / (label + ".key"),
            "-out",
            output / (label + ".pem"),
            "-subj",
            "/CN=Hearth RAM test " + label,
            "-addext",
            "basicConstraints=critical,CA:TRUE",
            "-addext",
            "keyUsage=critical,keyCertSign,cRLSign",
        )
    openssl(
        "req",
        "-new",
        "-newkey",
        "rsa:2048",
        "-noenc",
        "-keyout",
        output / "server.key",
        "-out",
        output / "server.csr",
        "-subj",
        "/CN=Hearth synthetic loopback server",
    )
    for label, ca in (("main", "ca"), ("other", "other-ca")):
        database = output / label
        database.mkdir(mode=0o700)
        (database / "index").write_text("")
        (database / "index.attr").write_text("unique_subject = no\n")
        (database / "serial").write_text("1000\n")
        (database / "crlnumber").write_text("1000\n")
        (database / "ca.cnf").write_text(
            "[ca]\ndefault_ca=local\n[local]\n"
            f"database={database}/index\nnew_certs_dir={database}\n"
            f"serial={database}/serial\ncrlnumber={database}/crlnumber\n"
            f"private_key={output}/{ca}.key\ncertificate={output}/{ca}.pem\n"
            "default_md=sha256\npolicy=policy\ndefault_crl_days=365\n"
            "unique_subject=no\n[policy]\ncommonName=supplied\n"
            "[server]\nbasicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\nsubjectAltName=IP:127.0.0.1\n"
            "[wrong]\nbasicConstraints=critical,CA:FALSE\n"
            "keyUsage=critical,digitalSignature,keyEncipherment\n"
            "extendedKeyUsage=serverAuth\nsubjectAltName=IP:192.0.2.1\n"
        )
    config = output / "main/ca.cnf"
    for name, start, end, extension in (
        ("valid", "20290101000000Z", "20310101000000Z", "server"),
        ("wrong-host", "20290101000000Z", "20310101000000Z", "wrong"),
        ("expired", "20270101000000Z", "20280101000000Z", "server"),
        ("future", "20350101000000Z", "20360101000000Z", "server"),
    ):
        openssl(
            "ca",
            "-batch",
            "-notext",
            "-config",
            config,
            "-in",
            output / "server.csr",
            "-out",
            output / (name + ".pem"),
            "-startdate",
            start,
            "-enddate",
            end,
            "-extensions",
            extension,
        )
    for name, start, end, cfg in (
        ("good", "20291231000000Z", "20310101000000Z", config),
        ("expired", "20270101000000Z", "20280101000000Z", config),
        ("future", "20350101000000Z", "20360101000000Z", config),
        ("other", "20291231000000Z", "20310101000000Z", output / "other/ca.cnf"),
    ):
        openssl(
            "ca",
            "-gencrl",
            "-config",
            cfg,
            "-out",
            output / (name + ".crl"),
            "-crl_lastupdate",
            start,
            "-crl_nextupdate",
            end,
        )
    openssl(
        "ca", "-config", config, "-revoke", output / "valid.pem", "-crl_reason", "keyCompromise"
    )
    openssl(
        "ca",
        "-gencrl",
        "-config",
        config,
        "-out",
        output / "revoked.crl",
        "-crl_lastupdate",
        "20291231000000Z",
        "-crl_nextupdate",
        "20310101000000Z",
    )
    verified = []
    for case in CASES:
        certificate = {
            "wrong_host": "wrong-host",
            "expired_cert": "expired",
            "future_cert": "future",
        }.get(case, "valid")
        ca = "other-ca" if case == "wrong_ca" else "ca"
        crl = {
            "missing_issuer_crl": "other",
            "expired_crl": "expired",
            "future_crl": "future",
            "revoked_cert": "revoked",
        }.get(case, "good")
        result = openssl(
            "verify",
            "-attime",
            EPOCH,
            "-verify_ip",
            "127.0.0.1",
            "-CAfile",
            output / (ca + ".pem"),
            "-CRLfile",
            output / (crl + ".crl"),
            "-crl_check",
            output / (certificate + ".pem"),
            check=False,
        )
        if (result.returncode == 0) != (case == "valid"):
            raise ValueError(
                "synthetic certificate fixture did not meet its host baseline: " + case
            )
        verified.append(case)
    record = {
        "status": "synthetic-fixtures-host-verified",
        "epoch": EPOCH,
        "cases": verified,
        "target_files": sorted(TARGET_FILES),
        "target_sha256": {
            n: hashlib.sha256((output / n).read_bytes()).hexdigest() for n in sorted(TARGET_FILES)
        },
        "real_device_credentials": False,
        "native_execution": False,
    }
    (output / "fixtures.json").write_text(json.dumps(record, indent=2) + "\n")
    for path in output.rglob("*"):
        if path.is_file():
            path.chmod(0o600)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    generate(parser.parse_args().output)
