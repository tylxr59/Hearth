"""One literal NTP hostname/IPv4 address, never a configuration fragment."""

import ipaddress
import re

from backend.validation import Invalid

DEFAULT = "time.nist.gov"


def time_server(value=DEFAULT):
    if not isinstance(value, str) or not 1 <= len(value) <= 253 or not value.isascii():
        raise Invalid("Enter one NTP hostname or IPv4 address.")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        if re.fullmatch(r"[0-9.]+", value) or not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in value.split(".")
        ):
            raise Invalid(
                "Enter one NTP hostname or IPv4 address without a port or spaces."
            ) from None
        return value.lower()
    if (
        address.version != 4
        or address.is_unspecified
        or address.is_multicast
        or address.is_loopback
    ):
        raise Invalid("A reachable unicast IPv4 time server is required.")
    return str(address)
