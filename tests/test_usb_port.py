from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.validation import Invalid
from firmware.probe import port as usb_port
from installer import discovery, wizard


def device(root, name, vendor, product):
    path = root / name
    path.mkdir(parents=True)
    (path / "idVendor").write_text(vendor + "\n")
    (path / "idProduct").write_text(product + "\n")
    return path


@pytest.mark.parametrize("port", ("1-1", "3-2", "3-2.4", "12-1.2.3.4.5.6.7", "255-255"))
def test_valid_ports(port):
    assert usb_port.valid(port)


@pytest.mark.parametrize(
    "port",
    (
        "",
        "1",
        "usb1",
        "1-1:1.0",
        "0-1",
        "1-0",
        "01-1",
        "1-01",
        "1-1.",
        "1-1..2",
        "256-1",
        "1-256",
        "1-1.1.1.1.1.1.1.1",
        " 1-1",
        "1-1/../2-1",
        None,
        11,
    ),
)
def test_invalid_ports(port):
    assert not usb_port.valid(port)


def test_discovers_the_single_native_nest_and_ignores_hubs_interfaces_and_others(tmp_path):
    device(tmp_path, "usb1", "1d6b", "0002")  # root hub
    device(tmp_path, "1-1", "046d", "c52b")  # keyboard receiver on the measured port
    device(tmp_path, "3-2", "05e3", "0610")  # hub
    device(tmp_path, "3-2.4", "2464", "0002")  # the Nest behind that hub
    device(tmp_path, "3-2.4:1.0", "2464", "0002")  # its interface, not a device
    assert usb_port.candidates(tmp_path) == {"3-2.4": "native"}
    assert usb_port.discover(tmp_path) == "3-2.4"


def test_discovery_refuses_none_several_and_stale_rom(tmp_path):
    with pytest.raises(usb_port.NotFound):
        usb_port.discover(tmp_path)
    with pytest.raises(usb_port.NotFound):
        usb_port.discover(tmp_path / "missing")
    device(tmp_path, "1-1", "2464", "0002")
    device(tmp_path, "2-3", "2464", "0002")
    with pytest.raises(usb_port.Ambiguous, match="1-1, 2-3"):
        usb_port.discover(tmp_path)
    rom = tmp_path / "rom"
    device(rom, "1-1", "0451", "d00e")
    with pytest.raises(ValueError, match="ROM already active") as caught:
        usb_port.discover(rom)
    assert not isinstance(caught.value, (usb_port.NotFound, usb_port.Ambiguous))


def test_ram_gadget_counts_only_as_the_sole_candidate(tmp_path):
    device(tmp_path, "2-1", "0525", "a4a7")
    assert usb_port.discover(tmp_path) == "2-1"
    with pytest.raises(usb_port.NotFound):
        usb_port.discover(tmp_path, modes=("native",))
    device(tmp_path, "1-1", "2464", "0002")
    with pytest.raises(usb_port.Ambiguous):
        usb_port.discover(tmp_path)
    assert usb_port.discover(tmp_path, modes=("native",)) == "1-1"


def test_pin_is_fixed_for_the_session(monkeypatch, tmp_path):
    monkeypatch.setattr(usb_port, "_pinned", None)
    device(tmp_path, "4-1", "2464", "0002")
    assert usb_port.current(tmp_path) == "4-1"
    assert usb_port.pinned() == "4-1"
    assert usb_port.pin("4-1") == "4-1"
    with pytest.raises(ValueError, match="moved from USB port 4-1 to 1-1"):
        usb_port.pin("1-1")
    with pytest.raises(ValueError, match="known USB port"):
        usb_port.pin("../1-1")
    assert usb_port.current(tmp_path / "missing") == "4-1"


def test_native_disk_can_be_limited_to_the_pinned_port(tmp_path):
    usb = tmp_path / "devices"
    for name in ("1-1", "3-2"):
        disk = device(usb, name, "2464", "0002") / "host0/block/sd" / name
        disk.mkdir(parents=True)
    block = tmp_path / "block"
    block.mkdir()
    (block / "sda").symlink_to(usb / "1-1/host0/block/sd/1-1")
    (block / "sdb").symlink_to(usb / "3-2/host0/block/sd/3-2")
    with pytest.raises(Invalid):
        discovery.native_disk(block, Path("/dev"))
    assert discovery.native_disk(block, Path("/dev"), port="3-2") == Path("/dev/sdb")
    assert discovery.native_disk(block, Path("/dev"), port="1-1") == Path("/dev/sda")
    with pytest.raises(Invalid):
        discovery.native_disk(block, Path("/dev"), port="2-1")


def test_find_nest_pins_the_port_and_warns_off_the_measured_port(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(usb_port, "_pinned", None)
    device(tmp_path, "3-2", "2464", "0002")
    assert wizard.find_nest(tmp_path) == "3-2"
    assert usb_port.pinned() == "3-2"
    out = capsys.readouterr().out
    assert "USB port 3-2" in out and "only been tested" in out


def test_find_nest_on_the_measured_port_has_no_warning(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(usb_port, "_pinned", None)
    device(tmp_path, "1-1", "2464", "0002")
    assert wizard.find_nest(tmp_path) == "1-1"
    assert "only been tested" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("devices", "message"),
    (
        ((), "No Nest found over USB"),
        ((("1-1", "2464", "0002"), ("2-1", "2464", "0002")), "one Nest connected"),
        ((("1-1", "0451", "d00e"),), "boot mode from an earlier run"),
        ((("1-1", "0525", "a4a7"),), "boot mode from an earlier run"),
    ),
)
def test_find_nest_explains_each_refusal(monkeypatch, tmp_path, devices, message):
    monkeypatch.setattr(usb_port, "_pinned", None)
    for row in devices:
        device(tmp_path, *row)
    with pytest.raises(Invalid, match=message):
        wizard.find_nest(tmp_path)
    assert usb_port.pinned() is None


ACL = Path("/usr/bin/setfacl")


def test_rule_for_the_measured_port_is_unchanged():
    # Existing installs already carry this exact rule; it must still match.
    assert wizard.usb_rules("1-1", 1000, ACL) == (
        b'ACTION=="add", SUBSYSTEM=="usb", ENV{DEVTYPE}=="usb_device", KERNEL=="1-1", '
        b'ATTR{idVendor}=="0451", ATTR{idProduct}=="d00e", MODE="0600", '
        b'RUN+="/usr/bin/setfacl -m u:1000:rw $env{DEVNAME}"\n'
        b'ACTION=="add", SUBSYSTEM=="tty", KERNEL=="ttyACM[0-9]*", KERNELS=="1-1", '
        b'ATTRS{idVendor}=="0525", ATTRS{idProduct}=="a4a7", MODE="0600", '
        b'RUN+="/usr/bin/setfacl -m u:1000:rw $env{DEVNAME}"\n'
    )


def test_previous_port_accepts_only_an_unmodified_hearth_rule_for_this_user():
    rule = wizard.usb_rules("3-2.4", 1000, ACL)
    assert wizard.previous_port(rule, 1000, ACL) == "3-2.4"
    assert wizard.previous_port(rule, 1001, ACL) is None
    assert wizard.previous_port(rule + b"# edited\n", 1000, ACL) is None
    assert wizard.previous_port(rule.replace(b"0600", b"0666"), 1000, ACL) is None
    bad = wizard.usb_rules("3-2.4", 1000, ACL).replace(b"3-2.4", b"3-2.*")
    assert wizard.previous_port(bad, 1000, ACL) is None
    assert wizard.previous_port(b"", 1000, ACL) is None


class Target:
    def __init__(self, content, uid=0, mode=0o100644):
        self.content, self.uid, self.mode = content, uid, mode

    def is_symlink(self):
        return False

    def exists(self):
        return self.content is not None

    def lstat(self):
        return SimpleNamespace(st_uid=self.uid, st_mode=self.mode)

    def read_bytes(self):
        return self.content

    def __str__(self):
        return "/etc/udev/rules.d/70-hearth-wizard.rules"


class RootACL:
    def is_file(self):
        return True

    def is_symlink(self):
        return False

    def stat(self):
        return SimpleNamespace(st_uid=0, st_mode=0o100755)

    def __str__(self):
        return str(ACL)


def rule_env(monkeypatch, target, port):
    monkeypatch.setattr(usb_port, "_pinned", port)
    monkeypatch.setattr(
        wizard,
        "Path",
        lambda value: target if value.startswith("/etc/udev") else RootACL(),
    )
    monkeypatch.setattr(wizard.workflow, "identity", lambda: "native")
    calls = []
    monkeypatch.setattr(wizard.subprocess, "run", lambda command, **kw: calls.append(command))
    return calls


def test_rule_is_scoped_to_the_discovered_port(monkeypatch, tmp_path):
    calls = rule_env(monkeypatch, Target(None), "3-2.4")
    wizard.usb_access(tmp_path, lambda _: "y")
    content = (tmp_path / "70-hearth-wizard.rules").read_text()
    assert 'KERNEL=="3-2.4"' in content and 'KERNELS=="3-2.4"' in content
    assert "1-1" not in content and len(calls) == 2


def test_matching_root_rule_needs_no_prompt_or_sudo(monkeypatch, tmp_path):
    uid = wizard.os.getuid()
    calls = rule_env(monkeypatch, Target(wizard.usb_rules("3-2", uid, ACL)), "3-2")
    wizard.usb_access(tmp_path, lambda _: pytest.fail("no prompt expected"))
    assert not calls


def test_hearth_rule_for_another_port_is_replaced_only_with_consent(monkeypatch, tmp_path):
    uid = wizard.os.getuid()
    calls = rule_env(monkeypatch, Target(wizard.usb_rules("1-1", uid, ACL)), "3-2")
    with pytest.raises(Invalid, match="port 1-1 to use the existing rule"):
        wizard.usb_access(tmp_path, lambda _: "")
    assert not calls
    wizard.usb_access(tmp_path, lambda _: "y")
    assert len(calls) == 2
    content = (tmp_path / "70-hearth-wizard.rules").read_text()
    assert 'KERNEL=="3-2"' in content and 'KERNEL=="1-1"' not in content


@pytest.mark.parametrize(
    "target",
    (
        Target(b"# someone else's rule\n"),
        Target(wizard.usb_rules("1-1", 99999, ACL)),
        Target(None, uid=1000),
    ),
)
def test_foreign_or_unsafe_rules_are_never_replaced(monkeypatch, tmp_path, target):
    if target.content is None:
        target.content = wizard.usb_rules("1-1", wizard.os.getuid(), ACL)
    calls = rule_env(monkeypatch, target, "3-2")
    with pytest.raises(Invalid, match="review it"):
        wizard.usb_access(tmp_path, lambda _: "y")
    assert not calls


def test_loader_is_given_only_the_pinned_port(monkeypatch):
    from installer import ram_handoff

    monkeypatch.setattr(usb_port, "_pinned", "3-2.4")
    args = ram_handoff.loader_args(Path("/synthetic"))
    assert args[1:3] == ["-P", "3-2.4"]


def test_every_host_loader_call_passes_the_pinned_port():
    root = Path(__file__).resolve().parent.parent
    for path in (*root.glob("installer/*.py"), *root.glob("firmware/*/*.py")):
        text = path.read_text()
        calls = text.count('/ "omap_loader"),')
        assert text.count('"-P",\n') >= calls, path
    for path in root.glob("firmware/*/boot.sh"):
        for line in path.read_text().splitlines():
            if 'omap_loader" ' in line:
                assert "-P 1-1" in line, path
