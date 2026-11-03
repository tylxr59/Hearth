"""Download only the admin-authorized commissioning data; never follow redirects."""

import ipaddress
import urllib.request
from urllib.parse import urlsplit

from backend.validation import Invalid
from firmware.file_writer.run import save
from installer.bundle import read_bundle


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def frontend(origin, token):
    if not isinstance(origin, str) or not origin.isascii() or len(origin) > 2048:
        raise Invalid("bounded HA frontend origin required")
    if any(ord(ch) <= 32 or ord(ch) == 127 for ch in origin):
        raise Invalid("HA frontend origin without whitespace required")
    parsed = urlsplit(origin)
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise Invalid("HA frontend origin required, without credentials or path")
    if parsed.scheme == "http":
        try:
            address = ipaddress.ip_address(parsed.hostname)
        except ValueError as exc:
            raise Invalid("unencrypted HA download requires a literal private address") from exc
        if (
            not (address.is_private or address.is_loopback)
            or address.is_unspecified
            or address.is_multicast
            or address.is_link_local
        ):
            raise Invalid("unencrypted HA download requires private LAN address")
    if (
        not isinstance(token, str)
        or not token
        or len(token) > 8192
        or any(ord(ch) < 33 or ord(ch) > 126 for ch in token)
    ):
        raise Invalid("HA administrator access token required")
    return origin.rstrip("/"), urllib.request.build_opener(
        urllib.request.ProxyHandler({}), NoRedirect()
    )


def download(origin, token, output):
    origin, opener = frontend(origin, token)
    if output.parent.resolve() != output.parent.absolute() or output.parent.stat().st_mode & 0o077:
        raise Invalid("private destination directory required")
    request = urllib.request.Request(
        origin.rstrip("/") + "/api/hearth/commissioning",
        headers={"Authorization": "Bearer " + token},
    )
    with opener.open(request, timeout=30) as response:  # nosec B310
        raw = response.read(65537)
    read_bundle(raw)
    save(output.parent, output.name, raw)
