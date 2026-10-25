# Enforceable network model

Production device deployment is blocked. Before any future networked bench test, use an isolated router interface/VLAN dedicated to the thermostat, with no other untrusted peers on that L2 segment. Enable AP/client isolation or separate switch ports; a routed firewall cannot stop same-L2 attacks. Do not bridge the test VLAN into the household LAN. Disable IPv6 RA/DHCPv6 on it and enforce IPv6 drops at the router. Ensure no alternate Wi-Fi, wired uplink, DNS-over-HTTPS escape or management-forwarding exception exists.

External requirements (currently mandatory):

- Thermostat -> backend: only fixed private backend IPv4 TCP 8443, TLS mandatory when compatible client exists.
- Thermostat -> explicitly local DNS: TCP/UDP 53 only if needed. Local DNS must serve only local names, **not recursively forward arbitrary device queries to the internet**. The canonical simulator uses a literal address and needs no DNS.
- Thermostat -> explicitly local NTP: UDP 123 only, if required after clock validation.
- DHCP -> local router only; no WAN DHCP relay. ARP stays on the isolated L2.
- Drop every other thermostat-originated packet, including public IPs, all IPv6 and external weather/HTTPS/SSH.
- Drop new inbound connections to thermostat. Allow only established return traffic. No forwarding TCP 22, 23, 80, 443, 8000 or 8080 to it.
- Backend egress: only its configured local MQTT broker TCP 8883, local DNS/NTP if required by host. No runtime package/image pulls, weather service or external update requests. HA communicates via broker, not direct unauthenticated management.
- Broker: authenticated TLS listener; `allow_anonymous false`, per-user ACLs in homeassistant/mosquitto.acl. Restrict network access to HA/backend. No external broker exposure or bridges.

Generate exact router rules for a dedicated routed interface:

```sh
.venv/bin/python tools/network_policy.py --interface nest0 \
  --backend 192.168.50.2 --dns 192.168.50.1 --ntp 192.168.50.1 > build/hearth-router.nft
# Review and syntax-check on the ROUTER using its nft version:
nft --check --file build/hearth-router.nft
# Apply there only after local routing review and authorization.
```

The generated `inet hearth` input/forward hooks drop all unallowed traffic for nest0, including IPv6, and reject new forwarding towards it. Other interfaces retain policy accept in this dedicated table; this is a thermostat containment fragment, not a complete router firewall. If backend shares the router's own IP, this fragment does not permit its TLS port in input: use a separate routed backend or add a specifically reviewed input rule. Router-originated traffic uses output, not forward: restrict it separately if running untrusted services on the router. It does not enforce backend egress; implement that on the backend/router using its own interface/IP policy. Rules are not auto-installed. Test compatibility with existing NAT/routing/firewall tables. NATed thermometers behind shared identities are not sufficient peer isolation.

On-device IPv4 iptables/filter is enabled in the historical gtvhacker source config; installed tools/modules are unknown. xt state/conntrack matches are disabled there, so recipes relying on `-m state` are invalid without evidence. Do not install a default-drop OUTPUT rule until DNS/DHCP/NTP, return traffic, IPv6, suspend/resume and recovery are validated. No on-device policy is currently enforced or claimed; external requirements are an explicit release gate until a verified hardware profile exists.

Verification before release:

1. Capture both VLAN-side and WAN-side traffic on the router, e.g. `tcpdump -ni nest0 -w nest-bench.pcap`; separately capture/filter WAN for the thermostat's translated flow identity. Store captures privately.
2. Observe idle, local-ring adjustment, reboot, DNS failure, broker/backend outage, and clock failure. Log all denied flow metadata with rate limits; avoid payload logging.
3. Confirm no thermostat flow escapes the allowlist, even when Google's names resolve to public addresses or backend fails. Confirm local NTP/DNS are not externally proxying device identifiers.
4. Inspect actual listeners/processes, kernel configuration and routes on the bench unit with separately authorized read-only access. Do not assume our offline replacements disabled services until runtime verification.
5. Repeat with backend/HA internet removed. Native regulation, schedule and protective tests require the authorized hardware plan.
