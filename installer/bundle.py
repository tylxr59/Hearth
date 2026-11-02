"""Bounded commissioning data, never an executable downloaded from HA."""

import io
import json
import plistlib
import ssl
import zipfile
from datetime import datetime

from backend.registry import token_valid
from backend.validation import Invalid, endpoint, serial
from provisioning.intake import UniqueKeys, inspect_info

FORMAT = "hearth-commissioning-v1"


def read_bundle(raw, *, for_restore=False):
    if type(for_restore) is not bool:
        raise Invalid("explicit bundle purpose required")
    if not isinstance(raw, bytes) or len(raw) > 65536:
        raise Invalid("bounded commissioning ZIP required")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if len(members) != 3 or {m.filename for m in members} != {
                "commissioning.json",
                "ca.pem",
                "ca.crl",
            }:
                raise Invalid("unexpected commissioning bundle files")
            if any(m.file_size > 32768 or m.flag_bits & 1 for m in members):
                raise Invalid("bounded unencrypted commissioning data required")
            data = json.loads(archive.read("commissioning.json"))
            ca, crl = archive.read("ca.pem"), archive.read("ca.crl")
    except (ValueError, KeyError, zipfile.BadZipFile, RuntimeError) as exc:
        raise Invalid("invalid commissioning bundle") from exc
    if not isinstance(data, dict) or set(data) != {
        "format",
        "origin",
        "serial",
        "credential",
        "supported_model",
        "supported_version",
        "supported_partition",
        "certificate_expires",
    }:
        raise Invalid("commissioning schema required")
    if data["format"] != FORMAT or not token_valid(data["credential"]):
        raise Invalid("unique commissioning credential required")
    serial(data["serial"])
    endpoint(data["origin"])
    if (data["supported_model"], data["supported_version"], data["supported_partition"]) != (
        "Display-2.6",
        "5.9.4-5",
        "primary",
    ):
        raise Invalid("unsupported commissioning compatibility profile")
    try:
        expires = datetime.fromisoformat(data["certificate_expires"])
        if expires.tzinfo is None or (not for_restore and expires <= datetime.now(expires.tzinfo)):
            raise Invalid("commissioning certificate expired")
        ssl.create_default_context(cadata=ca.decode("ascii"))
    except (ValueError, UnicodeError, ssl.SSLError) as exc:
        raise Invalid("invalid commissioning trust") from exc
    if b"-----BEGIN X509 CRL-----" not in crl or b"PRIVATE KEY" in ca + crl:
        raise Invalid("public CA/CRL only in commissioning bundle")
    return data, ca, crl


def device_info(raw, bundle=None):
    inspect_info(raw)
    source = plistlib.loads(raw, fmt=plistlib.FMT_XML, dict_type=UniqueKeys)
    display = source.get("Display", {})
    if (display.get("Model"), display.get("SoftwareVersion"), display.get("ActivePartition")) != (
        "Display-2.6",
        "5.9.4-5",
        "primary",
    ):
        raise Invalid("only primary Display-2.6 firmware 5.9.4-5 is supported")
    ident = serial(display.get("SerialNumber"))
    if bundle is not None and bundle["serial"] != ident:
        raise Invalid("commissioning bundle belongs to another thermostat")
    return {
        "model": display["Model"],
        "software": display["SoftwareVersion"],
        "partition": display["ActivePartition"],
        "serial": ident,
    }
