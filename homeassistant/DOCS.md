# Home Assistant OS installation (laboratory only)

Hearth uses native MQTT discovery; no custom HA component, Google integration or cloud account is required. The package is experimental and does not yet communicate with a physical Nest. A real TLS Mosquitto flow with simulated devices is tested; Supervisor and HA Core entity creation still need validation on an HAOS installation.

## Install

1. Run `make addon` on Linux. Copy the generated `build/addon/hearth` directory into the HAOS local add-ons directory `/addons/hearth` using your existing authorized file-transfer workflow. Reload the local add-on store and install **Hearth Laboratory**. No public Git repository or publishing is needed. Do not start it before supplying configuration.
2. Configure a local MQTT broker with authenticated TLS on 8883, no anonymous access, and dedicated `hearth-bridge` and `homeassistant-hearth` accounts. Apply [mosquitto.acl](mosquitto.acl), adapting usernames; never grant a general `hearth/#` write permission to the backend. Configure HA's MQTT integration to connect using its own account and validate the local CA. Broker ACL administration differs by add-on; use its supported configuration mechanism. The bundled ACL is a Mosquitto fragment, not automatic broker provisioning.
3. Prepare `registry.json`, `admin.json` and the simulator's device.json using provisioning.cli on your host. Stop the backend when preparing or changing a registry offline. Keep admin.json and device.json on the provisioning host; the backend needs only registry.json, TLS material and MQTT config.
4. In the add-on's mapped configuration directory (typically `/addon_configs/local_hearth` for a local add-on; verify its actual slug), install:

   ```text
   registry.json
   mqtt.json
   tls/server.pem
   tls/server.key
   tls/mqtt-ca.pem
   ```

   `mqtt.json` contains host, port=8883, username, unique password and `ca: /config/tls/mqtt-ca.pem`. The backend server certificate SAN must match the local private IP selected in simulator configuration. Choose a dedicated private CA. See docs/development.md for laboratory certificates; do not disable TLS verification.
5. The container runs as UID/GID **10001:10001**. Ensure that identity owns the config directory and registry (registry writes use atomic replacement), that directories are mode 0700, and that registry/MQTT config/private keys are mode 0600. Transfer through a secure administrator workflow; never make credentials world-readable to work around permissions. Config is mounted writable solely for authenticated registry changes.
6. Network port 8443 is **disabled by default**. For simulation only, explicitly map it to a chosen HAOS port on your isolated LAN. Allow only the simulator and provisioning/admin host to reach it. Do not expose it through a public reverse proxy or WAN port-forward. The device VLAN security model is in docs/security/network.md. HA controls through MQTT and needs no API access.
7. Start the add-on, then run tools.simulator with its TLS endpoint and CA on the Linux host. Watch for the MQTT discovered climate device and verify current/target temperature, humidity, mode, action, firmware and availability. Fan is offered only if explicitly configured for the simulator. No hardware capability discovery is claimed.

There is no separate management UI or UI listener; Home Assistant is the user interface. Administrative API calls require a Bearer token, including from the internal network. No Supervisor token or ingress header grants API privileges. If a management UI is later added, it must be ingress-only and independently reviewed.

## Upgrade and rollback

Stop the add-on. Back up its private config directory offline; do not upload it or commit it. Save the previous container/source version and SHA256SUMS. Review changelog/security findings, rebuild from pinned inputs, reinstall/rebuild the local add-on, and start it with the existing registry. Existing registries remain readable; an optional `revoked` identifier list is saved on credential changes to preserve MQTT cleanup across restarts. Keep that field in private backups. It discards state/commands on restart and starts devices unavailable until they report again. Upgrade/restart does not send an old desired setpoint.

For rollback, stop the add-on and restore its previous image/source and compatible registry backup, explicitly resolving any credential rotations/revocations made after that backup. Restoring a registry can unintentionally re-enable revoked credentials: review before restarting. No firmware upgrade or recovery is performed by this add-on. A failed host upgrade must leave the real thermostat on native local control; that behavior remains a bench validation requirement.

## Diagnostics and removal

Authenticated GET `/v1/manage/devices` returns current state/capabilities/availability without credentials. No historical backend log/database exists. HA's recorder and MQTT persistence can store state: configure retention/exclusions separately. No secrets in ordinary logs; avoid enabling network/body debugging.

Revoke devices with authenticated DELETE, keep the bridge running until retained discovery/state deletion is observed, then stop/uninstall. Offline CLI revocation requires stopping/restarting the backend; its saved identifier list now drives cleanup on the next MQTT connection and future reconnects. The bridge removes retained `homeassistant/climate/hearth_SERIAL/config` and `hearth/SERIAL/state`, keeping availability retained offline. An older release may already have forgotten an orphan: explicitly revoke its known identity once, or use an authorized broker admin tool. Manual removal is also needed if uninstalling without another broker connection; remove remaining availability if complete topic deletion is desired. Clear discovery before removing the add-on to avoid ghost entities. Broker deletion does not erase HA recorder/history or offline backups.
