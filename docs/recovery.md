# Undo and recovery

## Undo a finished install

From the **same extracted Hearth folder** you used for setup, with the Nest
display off its base and plugged in by USB:

```sh
python3 provision.py --restore
```

Pick your saved installation from the list. The wizard then:

1. Checks the full flash backup, the saved original files and the restore images.
2. Restores the three network files, with a read-only check first and then a
   `RESTORE` prompt.
3. Restores the nine settings, trust and startup files the same way.
4. Reads every file back to verify it, then tells you when it's safe to restart.

After that, remove the Hearth integration in Home Assistant if you don't need
it any more. Restoring never deletes anything in HA and never sends a heating
command.

### What restore needs

- Your `private/setup-…` folder, unchanged.
- The matching `build/setup-…` folder. Restore currently checks images against
  it, so you need the same computer and folder.
- The same Hearth version you installed with. A copy of its source is saved in
  the private folder.

### When restore refuses

Restore puts back the exact original files from setup day. If the thermostat's
settings have changed since then (for example, you changed its configuration on
the device), the files no longer match what was saved, and restore **refuses
instead of overwriting** your current setup. That's deliberate. Don't try to
work around it. Open an [issue](https://github.com/tylxr59/Hearth/issues)
instead. Never attach your private files.

## If setup or restore stopped partway

1. **Keep USB connected.** Don't restart the Nest.
2. **Keep the private folder exactly as it is.**
3. Don't run setup or restore again. Old profiles are single-use, and a timeout
   doesn't mean nothing was written.
4. Ask for help, and describe which step stopped and the message it printed.

The low-level tools can recover one phase at a time
(`restore-kit --phase cleanup|commissioning`, see the
[advanced CLI](advanced-cli.md#restore)). That needs someone to review the saved
reports first. The tool won't guess which phase is right.

## What has and hasn't been tested

| Recovery | Status |
| --- | --- |
| Restoring the saved files and getting back to the stock Nest home screen | ✅ Done on the development unit |
| Full flash backup, with two passes cross-checked | ✅ Done |
| Writing a full flash backup back to the chip | ❌ Never tested, no tool for it |
| Recovering from a power cut during a write | ❌ Not tested |

The full flash backup is kept as a last-resort record, but nothing in Hearth can
write it back yet. A commissioning bundle is not a firmware backup, and a raw
flash copy is not proof that a restore works.
