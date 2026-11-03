"""Local address suggestions from HA metadata; never probes a network."""

import ipaddress
from urllib.parse import urlsplit


def candidate_origins(adapters, internal_url=None):
    addresses = {}
    if not isinstance(adapters, list):
        return []
    for adapter in adapters[:64]:
        if not isinstance(adapter, dict):
            continue
        rows = adapter.get("ipv4", [])
        if not isinstance(rows, list):
            continue
        for row in rows[:32]:
            try:
                address = ipaddress.IPv4Address(row["address"])
            except (KeyError, TypeError, ValueError):
                continue
            if (
                not address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_unspecified
                or address.is_multicast
                or address.is_reserved
            ):
                continue
            rank = (not adapter.get("enabled", False), not adapter.get("default", False))
            addresses[address] = min(rank, addresses.get(address, rank))
    try:
        preferred = ipaddress.IPv4Address(urlsplit(internal_url or "").hostname or "")
    except ValueError:
        preferred = None
    ordered = sorted(addresses, key=lambda a: (a != preferred, addresses[a], int(a)))
    return [f"https://{address}:8443" for address in ordered[:32]]
