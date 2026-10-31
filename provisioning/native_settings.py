"""Offline, byte-preserving assigned-credential preparation; no device I/O."""

import re

# DTDs and entities are rejected before expansion.
from xml.parsers import expat  # nosec B407

from backend.registry import token_valid
from backend.validation import Invalid, serial


def nist_time_config(data):
    """Redirect the single reviewed native NTP server, retaining all other bytes."""
    if not isinstance(data, bytes) or len(data) > 65536 or b"\0" in data:
        raise Invalid("bounded native NTP configuration required")
    servers = list(re.finditer(rb"(?m)^[ \t]*(?:server|pool|peer)\b[^\r\n]*", data))
    if len(servers) != 1 or servers[0][0] != b"server time.nest.com":
        raise Invalid("single reviewed native NTP server required")
    item = servers[0]
    return data[: item.start()] + b"server time.nist.gov minpoll 6 maxpoll 10" + data[item.end() :]


def assigned_credentials(data, ident, credential):
    """Replace exactly the two existing native settings value spans, atomically in RAM."""
    serial(ident)
    if not token_valid(credential):
        raise Invalid("unique assigned credential must contain 256 random bits")
    if not isinstance(data, bytes) or len(data) > 1024 * 1024:
        raise Invalid("bounded native settings bytes required")
    targets = {"assigned_cred_id": ident, "assigned_cred_secret": credential}
    parser = expat.ParserCreate()
    stack, seen, edits = [], set(), []

    def reject(*args):
        raise Invalid("native settings DTDs and entities are unsupported")

    def declaration(version, encoding, standalone):
        if version != "1.0" or (encoding and encoding.lower() not in ("utf-8", "iso-8859-1")):
            raise Invalid("unsupported native settings encoding")

    def start(name, attrs):
        stack.append(name)
        if len(stack) == 1:
            if name != "settings" or attrs:
                raise Invalid("native settings root required")
            return
        if stack != ["settings", "s"] or set(attrs) != {"key", "value"}:
            raise Invalid("unsupported native settings structure")
        key = attrs["key"]
        if key in seen:
            raise Invalid("duplicate native setting")
        seen.add(key)
        if key not in targets:
            return
        offset = parser.CurrentByteIndex
        tag = re.match(rb"""<s\b(?:[^"'<>]|"[^"]*"|'[^']*')*/>""", data[offset:])
        if tag is None:
            raise Invalid("literal self-closing credential entry required")
        value = re.search(rb"""\bvalue\s*=\s*(["'])(.*?)\1""", tag[0], re.DOTALL)
        if value is None:
            raise Invalid("literal credential value required")
        edits.append((offset + value.start(2), offset + value.end(2), targets[key].encode("ascii")))

    parser.StartDoctypeDeclHandler = reject
    parser.EntityDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.XmlDeclHandler = declaration
    parser.StartElementHandler = start
    parser.EndElementHandler = lambda name: stack.pop()
    parser.CharacterDataHandler = lambda value: reject() if value.strip() else None
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise Invalid("invalid native settings XML") from exc
    if not targets.keys() <= seen:
        raise Invalid("both existing assigned credential entries required")
    for begin, end, value in sorted(edits, reverse=True):
        data = data[:begin] + value + data[end:]
    return data
