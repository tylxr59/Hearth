import hashlib
import tarfile
from pathlib import Path

from tools.demo_artifacts import demo
from tools.network_policy import policy
from tools.package_addon import package
from tools.release import release


def test_demo_and_addon_assembly(tmp_path):
    root = Path(__file__).resolve().parents[1]
    demo(tmp_path / "demo")
    assert (
        (tmp_path / "demo/offline-replacements/replacement-files/etc/shadow")
        .read_text()
        .startswith("root:!:")
    )
    addon = package(tmp_path / "addon")
    assert (addon / "backend/api.py").read_bytes() == (root / "backend/api.py").read_bytes()
    assert (addon / "requirements.lock").read_bytes() == (root / "requirements.lock").read_bytes()
    assert (addon / "Dockerfile").is_file()
    assert not list(addon.rglob("device.json"))


def test_reproducible_source_archive(tmp_path):
    one, two = tmp_path / "one", tmp_path / "two"
    assert release(one) == release(two)
    with tarfile.open(one / "hearth-0.1.0-source.tar") as archive:
        assert all(info.uid == 0 and info.mtime == 0 for info in archive.getmembers())
        assert all(
            "private/" not in name and "__pycache__" not in name for name in archive.getnames()
        )
    for line in (one / "SHA256SUMS").read_text().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256((one / name).read_bytes()).hexdigest() == digest


def test_router_policy_ipv6_and_ingress_are_denied():
    text = policy("nest0", "192.168.50.2", "192.168.50.1", "192.168.50.1")
    assert "table inet hearth" in text
    assert 'iifname "nest0" drop' in text
    assert 'oifname "nest0" drop' in text
    assert "tcp dport 8443 accept" in text
    assert "ct state established,related accept" in text
