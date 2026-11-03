"""Read-only USB identity to the admin-authorized HA config flow; no firmware I/O."""

import json
import re
import time
import urllib.error
import urllib.request

from backend.validation import Invalid, endpoint
from firmware.file_writer.run import encode, save
from installer import ui
from installer.bundle import device_info, read_bundle
from installer.download import frontend
from tools.elf_review import private_path

FLOW = "/api/config/config_entries/flow"


class HAClient:
    def __init__(self, origin, token):
        self.origin, self.opener = frontend(origin, token)
        self.headers = {"Authorization": "Bearer " + token}

    def request(self, method, path, data=None):
        request = urllib.request.Request(
            self.origin + path,
            data=None if data is None else encode(data),
            headers=self.headers
            | ({"Content-Type": "application/json"} if data is not None else {}),
            method=method,
        )
        with self.opener.open(request, timeout=30) as response:  # nosec B310
            raw = response.read(65537)
        if len(raw) > 65536:
            raise Invalid("bounded HA setup response required")
        return raw

    def flow(self, path, data):
        value = json.loads(self.request("POST", path, data))
        if not isinstance(value, dict) or value.get("handler") != "hearth":
            raise Invalid("Hearth setup response required")
        return value

    def bundle(self):
        deadline = time.monotonic() + 15
        while True:
            try:
                return self.request("GET", "/api/hearth/commissioning")
            except urllib.error.HTTPError as exc:
                if exc.code not in (404, 503) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)  # Only the read-only bundle fetch may retry.


def choices(form):
    fields = form.get("data_schema")
    if fields == []:
        # HA offers an empty form when config/.storage/hearth already exists:
        # removing the integration keeps the old profile and its credential.
        raise Invalid(
            "Home Assistant still has a saved Hearth profile from an earlier install "
            "(config/.storage/hearth). Move that folder aside (don't delete it; it holds "
            "the old credential), then run setup again. No restart is needed."
        )
    if (
        not isinstance(fields, list)
        or len(fields) != 2
        or any(not isinstance(field, dict) for field in fields)
        or {f.get("name") for f in fields} != {"origin", "device_id"}
    ):
        raise Invalid(
            "fresh Hearth setup required; close existing dialogs or preserve existing profile"
        )
    field = next(f for f in fields if f["name"] == "origin")
    selector = field.get("selector", {})
    if not isinstance(selector, dict) or not isinstance(selector.get("select", {}), dict):
        raise Invalid("local endpoint selection schema required")
    values = selector.get("select", {}).get("options", [])
    if not isinstance(values, list) or len(values) > 32:
        raise Invalid("bounded local endpoint suggestions required")
    return list(dict.fromkeys(endpoint(value) for value in values))


def onboard(ha_url, token, session, info, *, target=None, ask=input, client=None):
    identity = device_info(info)
    session = private_path(session)
    if session.exists() or not session.parent.is_dir() or session.parent.stat().st_mode & 0o077:
        raise Invalid("fresh session beneath an owner-only private directory required")
    if target is not None:
        target = endpoint(target)
    client = HAClient(ha_url, token) if client is None else client
    session.mkdir(mode=0o700)
    save(session, "identity.json", encode(identity))
    form = client.flow(FLOW, {"handler": "hearth"})
    save(session, "onboarding-form.json", encode(form))
    flow_id = form.get("flow_id")
    if (
        form.get("type") != "form"
        or form.get("step_id") != "user"
        or not isinstance(flow_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", flow_id)
    ):
        raise Invalid("fresh user setup required; close any open Hearth setup dialog first")
    options = choices(form)
    if target is None:
        ui.section("Which address should the Nest use to reach Home Assistant?")
        ui.say(
            "Home Assistant listens for the Nest on these addresses. Pick the one on the "
            "same network as the thermostat, or type a different https:// address."
        )
        ui.numbered(options)
        answer = ask(
            ui.prompt(
                "Address number or https:// address", "[Enter = 1]" if len(options) == 1 else None
            )
        ).strip()
        if not answer and len(options) == 1:
            target = options[0]
        elif answer.isdecimal() and 1 <= int(answer) <= len(options):
            target = options[int(answer) - 1]
        else:
            target = endpoint(answer)
    ui.ok(f"The Nest will connect to Home Assistant at {target}.")
    if (
        ask(ui.prompt("Type SETUP to add Hearth to Home Assistant", "[Enter = cancel]")).strip()
        != "SETUP"
    ):
        client.request("DELETE", FLOW + "/" + flow_id)
        save(
            session,
            "onboarding-cancelled.json",
            encode({"cancelled": True, "firmware_written": False}),
        )
        return {"cancelled": True, "firmware_written": False}
    result = client.flow(FLOW + "/" + flow_id, {"origin": target, "device_id": identity["serial"]})
    save(session, "onboarding-result.json", encode(result))
    if result.get("type") != "create_entry":
        raise Invalid("HA refused setup; preserve this session and do not automatically resubmit")
    raw = client.bundle()
    save(session, "commissioning-response.zip", raw)
    bundle, _, _ = read_bundle(raw)
    if bundle["serial"] != identity["serial"] or bundle["origin"] != target:
        raise Invalid("HA bundle differs from this USB identity or selected endpoint")
    save(session, "commissioning.zip", raw)
    status = {
        "ha_configured": True,
        "usb_identity_read": True,
        "private_session_prepared": True,
        "firmware_written": False,
    }
    save(session, "onboarding-complete.json", encode(status))
    return status
