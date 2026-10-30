import json
import plistlib

import pytest

from backend.validation import Invalid
from provisioning.intake import MAX_INFO_BYTES, inspect_info, usb_events, usb_inventory


def test_diagnostic_output_excludes_identifiers_and_unknown_fields():
    data = plistlib.dumps(
        {
            "Base": {"Model": "unknown"},
            "Display": {
                "Model": "Display-2.6",
                "SoftwareVersion": "5.9.4-5",
                "ActivePartition": "primary",
                "SoftwareUpdateState": "Synchronized - None",
                "SerialNumber": "PRIVATE_SERIAL",
                "Credentials": "PRIVATE_CREDENTIALS",
            },
            "Network": {"MACAddress": "PRIVATE_MAC", "SSID": "PRIVATE_SSID"},
        }
    )
    report = inspect_info(data)
    assert report["metadata"]["Display"]["Model"] == "Display-2.6"
    assert report["metadata"]["Display"]["SoftwareVersion"] == "5.9.4-5"
    assert report["metadata"]["Base"] == {"Model": "unknown"}
    assert "PRIVATE" not in json.dumps(report)
    assert "Network" not in report["metadata"]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"<",
        b"x" * (MAX_INFO_BYTES + 1),
        plistlib.dumps(["not a dictionary"]),
        plistlib.dumps({"Display": "wrong section type"}),
        plistlib.dumps({"Display": {"Model": 2}}),
        plistlib.dumps({"Display": {"Model": "value\nwith controls"}}),
        plistlib.dumps({"Display": {"Model": "x" * 97}}),
        plistlib.dumps({"Network": {"SSID": "PRIVATE"}}),
        (
            b"<plist><dict><key>Display</key><dict><key>Model</key><string>a</string>"
            b"<key>Model</key><string>b</string></dict></dict></plist>"
        ),
        (
            b'<!DOCTYPE plist [<!ENTITY secret "PRIVATE">]><plist><dict>'
            b"<key>Display</key><dict><key>Model</key><string>&secret;</string>"
            b"</dict></dict></plist>"
        ),
    ],
)
def test_diagnostic_rejects_malformed_or_ambiguous_input(data):
    with pytest.raises(Invalid) as error:
        inspect_info(data)
    assert "PRIVATE" not in str(error.value)


def usb_device(root, vendor, product, name="1-1"):
    path = root / name
    path.mkdir(exist_ok=True)
    (path / "idVendor").write_text(vendor)
    (path / "idProduct").write_text(product)
    (path / "serial").write_text("PRIVATE_SERIAL")


def test_observed_usb_modes_do_not_claim_compatibility(tmp_path):
    for vendor, product, mode in (
        ("2464", "0002", "nest-mass-storage"),
        ("0451", "d00e", "omap-rom-candidate"),
        ("0451", "1234", "ti-candidate"),
    ):
        usb_device(tmp_path, vendor, product)
        result = usb_inventory(tmp_path)
        assert len(result) == 1
        assert result[0]["mode"] == mode
        assert result[0]["compatible"] is False
        assert result[0]["generation"] == "unknown"
        assert "PRIVATE_SERIAL" not in json.dumps(result)
    usb_device(tmp_path, "18d1", "4e11")
    assert usb_inventory(tmp_path) == []
    usb_device(tmp_path, "0451", "d00e\nPRIVATE_SERIAL")
    assert usb_inventory(tmp_path) == []


def test_usb_watch_records_disconnect_rom_and_return_without_duplicate_events(
    tmp_path, monkeypatch
):
    from provisioning import intake

    clock = [0.0]
    usb_device(tmp_path, "2464", "0002")

    def advance(_):
        clock[0] = round(clock[0] + 0.05, 2)
        if clock[0] == 0.1:
            (tmp_path / "1-1/idVendor").unlink()
        elif clock[0] == 0.2:
            usb_device(tmp_path, "0451", "d00e")
        elif clock[0] == 0.3:
            usb_device(tmp_path, "2464", "0002")

    monkeypatch.setattr(intake.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(intake.time, "sleep", advance)
    events = list(usb_events(1, tmp_path))
    assert len(events) == 4
    assert [e["devices"][0]["product"] if e["devices"] else None for e in events] == [
        "0002",
        None,
        "d00e",
        "0002",
    ]


@pytest.mark.parametrize("seconds", [0, -1, 301, True, float("nan"), float("inf")])
def test_usb_watch_is_bounded(seconds):
    with pytest.raises(Invalid):
        list(usb_events(seconds))
