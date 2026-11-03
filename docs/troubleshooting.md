# Troubleshooting

> [!CAUTION]
> When asking for help, **never post** your private setup folder,
> `commissioning.zip`, raw logs, the thermostat's serial number or any tokens.
> Hearth's diagnostics download in Home Assistant is safe to share: it contains
> no payloads or identifiers.

## Setup wizard

| Problem | Fix |
| --- | --- |
| "Some tools this wizard needs are missing" | Run the install command it prints, then start the wizard again |
| "Run this wizard as your normal user" | Don't use `sudo python3 provision.py`. The wizard asks for sudo itself when it needs it |
| "No Nest found in normal mode on USB port 1-1" | Use a **data** cable. Plug into the port Linux calls `1-1` (usually the first root port; `lsusb -t` shows it). Wait for the Nest to finish booting |
| "Your account can't read the Nest's info file" | Answer `y` to allow one read-only `sudo mtype` |
| Asked for a USB permission rule | Answer `y`. This adds a rule just for your user on port 1-1. It doesn't grant disk write access |
| HA step says "fresh user setup required" | Close any open Hearth dialog in HA, and make sure no Hearth entry already exists |
| HA step says HA "still has a saved Hearth profile" | Removing the integration keeps `config/.storage/hearth`. Move it aside (for example `mv /config/.storage/hearth /config/hearth-profile-backup`) and run setup again. Don't delete it, because it holds the old credential |
| Home Assistant address refused | Use the full address with port, e.g. `http://192.168.1.10:8123`. Plain HTTP must be a private IP |
| Stuck at "The loader is waiting now" | Hold the ring **10 seconds**, let go, then press once. Keep the display off its base |
| Build step failed | Check the `.log` in your private folder. Common causes are no internet, too little disk space or Podman not working rootless |
| Kit step says an existing installation was found | That Nest already has Hearth (or part of it). The wizard only installs on stock units |
| Space check refused | The Nest's flash is too full for a safe install. The wizard shows how much is needed and how much is free. Nothing was written, so restart the Nest normally when it says so. Please report the numbers in an issue |

### Setup stopped partway

Everything before step 6 is read-only, so the Nest is unchanged. Keep the
private folder, unplug or restart the Nest normally once the wizard has exited,
and ask for help before trying again.

If it stopped during **step 6 (Install)**:

1. Keep USB connected. Don't restart the Nest.
2. Keep the private folder exactly as it is.
3. Don't run the wizard again. Follow [recovery](recovery.md#if-setup-or-restore-stopped-partway).

## Home Assistant

| Problem | Fix |
| --- | --- |
| No readings / entities unavailable | Check the Nest has power and Wi-Fi. Check it can reach HA on port **8443** (HTTPS) and HA's HTTP port (8123), especially across VLANs |
| Readings stopped after an HA restart | Wake the Nest by pressing the ring once. It should reconnect without a reboot |
| Target shows as "assumed" | The Nest accepted the command but hasn't reported the new value back yet. Its report wins when it arrives |
| A setting entity is missing or unknown | Your Nest doesn't report that field, or your equipment doesn't support it. Hearth never guesses |
| An equipment setting is disabled | Equipment-affecting entities start disabled. Enable them deliberately in the entity settings |
| Schedule replace refused: revision changed | Run **Read weekly schedule** again and use the new revision. Don't resubmit an old action |
| Schedule shows `unconfirmed` | A change expired without the Nest confirming it. Read the schedule again before editing |
| Weather missing on the Nest | Pick a weather entity under Hearth's **Configure** options and set the fallback postal code and country |

For deeper debugging, Hearth's diagnostics (on the device page, **Download
diagnostics**) show active subscriptions, rejection counts and command status.
