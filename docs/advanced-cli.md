# Advanced CLI

The setup wizard (`python3 provision.py`) runs every step below in order, with
the right checks between them. Most people should use the wizard. This page is
for developers, and for anyone who needs to run or inspect one step on its own.

All commands use `python3 -m installer.cli <command>` from an extracted
installer folder, or `.venv/bin/python -m installer.cli <command>` (also
available as `hearth <command>`) in a development checkout. Run
`--help` on any command for every option.

> [!IMPORTANT]
> The same safety rules apply here as in the wizard: each USB boot step runs
> **once**, nothing is retried automatically, and every write asks for its own
> confirmation. Never delete a failed attempt's folder so you can reuse its path.

## Command map

| Stage | Command | Touches the Nest? |
| --- | --- | --- |
| Check this computer | `doctor` | No |
| Read the Nest's identity | `identify --disk /dev/sdX` | Read-only USB disk |
| Create the HA entry | `onboard --ha-url URL --session DIR` | Read-only USB disk |
| Download an existing bundle | `download --ha-url URL --output FILE` | No |
| Check a bundle against a Nest | `setup --bundle ZIP --info PLIST --session DIR` | No |
| Fetch pinned sources | `sources --output DIR` | No |
| Build the read-only reader | `build-reader --sources DIR --output DIR --profile DIR` | No |
| Read the original files | `acquire --session DIR --profile DIR --disk /dev/sdX` | Read-only USB boot |
| Verify what was read | `check-inputs --session DIR` | No |
| Build your kit | `build-kit --session DIR --sources DIR --reader-build DIR --build DIR --output DIR` | No |
| Check a kit | `check-kit --kit DIR [--for-restore]` | No |
| Install | `install-kit --kit DIR --disk /dev/sdX` | **Writes flash** |
| Restore | `restore-kit --kit DIR --disk /dev/sdX` | **Writes flash** |

`/dev/sdX` is the Nest's small diagnostic disk. Look it up. Don't guess.

## Identity and Home Assistant

```sh
python3 -m installer.cli doctor
python3 -m installer.cli identify --disk /dev/sdX            # add --show-device-id to print the serial
python3 -m installer.cli onboard --ha-url http://YOUR_HA_IP:8123 --session private/my-install
```

`onboard` is described in the
[install guide](installation.md#automatic-usb-onboarding). If your account can't
read the Nest's diagnostic file, either add `--sudo-read`, which runs one fixed,
read-only `sudo mtype`, or save `Technical Info.plist` yourself and pass
`--info PATH`. Never give your account write access to the block device.

To fetch the commissioning bundle for an existing HA entry:

```sh
python3 -m installer.cli download --ha-url https://YOUR_HA_IP --output private/commissioning.zip
```

This calls `/api/hearth/commissioning` with a hidden HA admin token. It refuses
redirects and saves the file with mode 0600. The ZIP holds the thermostat's
credential and HA's public CA/CRL, never HA's private keys. Treat it as a
password.

## Build and read the originals

```sh
python3 -m installer.cli sources --output build/installer-sources
python3 -m installer.cli build-reader --sources build/installer-sources \
  --output build/installer-reader --profile private/my-reader
python3 -m installer.cli acquire --session private/my-install \
  --profile private/my-reader --disk /dev/sdX
python3 -m installer.cli check-inputs --session private/my-install
```

- Only `sources` and the container image build need the internet. The kernel
  compiles with no network, no USB and no access to `private/`.
- `acquire` asks for `READY`, then you press the ring when told. It reads two
  filesystem snapshots and the native libraries into `private/`. It never runs
  a writer or the Nest's own software, and nothing acquired is executed on your
  computer.
- `check-inputs` rebuilds every saved frame and checks the files and receipts.
  It refuses anything modified, missing or extra.

To go straight on to installing, keep USB connected and don't restart the Nest.
Otherwise, follow the command's restart instructions. Native startup can change
settings, which makes the saved snapshot stale.

The wizard also takes a full flash backup before this step
(`installer/nand_backup.py`). Running these steps by hand doesn't include that
backup.

## Build and check the kit

```sh
python3 -m installer.cli build-kit --session private/my-install \
  --sources build/installer-sources --reader-build build/installer-reader \
  --build build/my-kit --output private/my-kit
python3 -m installer.cli check-kit --kit private/my-kit
```

The kit holds one install image (a free-space check, then two groups of files:
nine settings, trust and startup files, then three network/time files) and
matching restore images for each group. It's tied to this one thermostat, its
originals and its HA bundle. A kit from another unit, a kit that has already
been used or a changed source recipe is refused. See
[firmware kit internals](development/firmware-kit.md).

## Install

```sh
python3 -m installer.cli install-kit --kit private/my-kit --disk /dev/sdX
```

Everything runs in one USB boot:

1. Answer `y` to start, then press the ring when told.
2. Free-space check for both groups. Read-only, nothing can be written.
3. First group: nine files. The tool checks the originals on the Nest, then
   `INSTALL` writes them and every file is checked.
4. Second group: three files. Same as the first. It starts only if the first
   group was written and verified.

Restart the Nest only when the tool says it's safe to. Only USB port **1-1**
is supported for now.

## Restore

```sh
python3 -m installer.cli check-kit --kit private/my-kit --for-restore
python3 -m installer.cli restore-kit --kit private/my-kit --disk /dev/sdX
```

The three network files are restored first, then the nine others. Each part
gets its own read-only check and `RESTORE` prompt. `--phase cleanup` and
`--phase commissioning` exist to recover an install that stopped partway. Use
them only after the saved reports have been reviewed. The tool never guesses
which one is right. See [undo and recovery](recovery.md).
