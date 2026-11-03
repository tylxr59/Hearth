# Hearth Nest installer

This folder sets up Hearth on a **Nest Learning Thermostat (2nd gen,
Display-2.6, software 5.9.4-5)** over USB, from a Linux computer.

> **Experimental preview.** Read the install guide before you start.

## Start here

1. Take the Nest display off its wall base and plug it into this computer by USB.
2. Open a terminal in this folder and run:

   ```sh
   python3 provision.py
   ```

3. Follow the wizard. It checks your computer and tells you what to install if
   anything is missing. It asks before every write to the thermostat.

To undo a previous install, run `python3 provision.py --restore` from **this
same folder**.

## Keep this folder

After setup, this folder contains `private/` (your backups and install kit)
and `build/`. Restoring needs both, plus these files, on the same computer.
Never share `private/`: it contains your thermostat's credential.

## Guides

- `docs/installation.md`: full install guide
- `docs/troubleshooting.md`: common problems
- `docs/recovery.md`: undo and recovery
- `docs/advanced-cli.md`: running each step by hand

Online: https://github.com/tylxr59/Hearth

The Home Assistant integration is installed separately through HACS. The
wizard walks you through it.
