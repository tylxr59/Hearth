"""Print an external Linux router policy; never install firewall rules automatically."""

import argparse
import ipaddress
import re


def policy(interface, backend, dns, ntp):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,15}", interface):
        raise ValueError("invalid interface")
    for address in (backend, dns, ntp):
        parsed = ipaddress.IPv4Address(address)
        if not parsed.is_private or parsed.is_unspecified or parsed.is_multicast:
            raise ValueError("private unicast addresses required")
    return f'''# Review on the ROUTER; never run on a thermostat. Dedicated isolated VLAN only.
# Remove any broad allow rules that bypass this policy in the router's other tables.
table inet hearth {{
  chain input {{
    type filter hook input priority -10; policy accept;
    iifname "{interface}" udp sport 68 udp dport 67 accept
    iifname "{interface}" ip daddr {dns} udp dport 53 accept
    iifname "{interface}" ip daddr {dns} tcp dport 53 accept
    iifname "{interface}" ip daddr {ntp} udp dport 123 accept
    iifname "{interface}" drop
  }}
  chain forward {{
    type filter hook forward priority -10; policy accept;
    iifname "{interface}" ip daddr {backend} tcp dport 8443 accept
    iifname "{interface}" ip daddr {dns} udp dport 53 accept
    iifname "{interface}" ip daddr {dns} tcp dport 53 accept
    iifname "{interface}" ip daddr {ntp} udp dport 123 accept
    iifname "{interface}" drop
    oifname "{interface}" ct state established,related accept
    oifname "{interface}" drop
  }}
}}
'''


def main():
    parser = argparse.ArgumentParser()
    for name in ("interface", "backend", "dns", "ntp"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(policy(args.interface, args.backend, args.dns, args.ntp))


if __name__ == "__main__":
    main()
