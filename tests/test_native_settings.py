import xml.etree.ElementTree as ET

import pytest

from backend.validation import Invalid
from provisioning.native_settings import assigned_credentials
from tests.conftest import SERIAL

TOKEN = "a" * 64


def settings(encoding="ISO-8859-1"):
    return (
        f'<?xml version="1.0" encoding="{encoding}"?>\r\n'
        '<settings>\r\n<!-- assigned_cred_secret value="leave comment" -->\r\n'
        '<s value="old&amp;id" key="assigned_cred_id"/>\r\n'
        "<s key='assigned_cred_secret' value='old&amp;secret'/>\r\n"
        '<s key="unknown" value="caf&#233; &amp; untouched"/>\r\n</settings>\r\n'
    ).encode("ascii")


@pytest.mark.parametrize("encoding", ["ISO-8859-1", "UTF-8"])
def test_only_two_credential_values_change(encoding):
    original = settings(encoding)
    result = assigned_credentials(original, SERIAL, TOKEN)
    assert result == original.replace(b"old&amp;id", SERIAL.encode()).replace(
        b"old&amp;secret", TOKEN.encode()
    )
    values = {x.attrib["key"]: x.attrib["value"] for x in ET.fromstring(result)}
    assert values["assigned_cred_id"] == SERIAL
    assert values["assigned_cred_secret"] == TOKEN
    assert assigned_credentials(result, SERIAL, TOKEN) == result


def test_non_ascii_native_bytes_remain_unchanged():
    original = settings().replace(b"caf&#233;", b"caf\xe9")
    assert b"caf\xe9" in assigned_credentials(original, SERIAL, TOKEN)


@pytest.mark.parametrize(
    "bad",
    [
        lambda x: x.replace(b"<settings>", b'<settings extra="yes">'),
        lambda x: x.replace(b"</settings>", b'<s key="unknown" value="duplicate"/></settings>'),
        lambda x: x.replace(
            b"</settings>", b'<s key="assigned_cred_id" value="duplicate"/></settings>'
        ),
        lambda x: x.replace(b"<s key='assigned_cred_secret' value='old&amp;secret'/>", b""),
        lambda x: x.replace(b"ISO-8859-1", b"UTF-16"),
        lambda x: x.replace(b"<settings>", b'<!DOCTYPE settings [<!ENTITY secret "x">]><settings>'),
        lambda x: x.replace(b"</settings>", b"<nested/></settings>"),
        lambda x: x.replace(b"</settings>", b"unexpected text</settings>"),
        lambda x: x.replace(b"value='old&amp;secret'/>", b"value='old&amp;secret'></s>"),
        lambda x: x[:-20],
        lambda x: b" " * (1024 * 1024 + 1),
    ],
)
def test_ambiguous_or_unsupported_settings_fail_before_output(bad):
    with pytest.raises(Invalid):
        assigned_credentials(bad(settings()), SERIAL, TOKEN)


@pytest.mark.parametrize("token", ["short", "A" * 64, "a" * 63, None])
def test_invalid_credential_never_enters_settings(token):
    with pytest.raises(Invalid):
        assigned_credentials(settings(), SERIAL, token)


def test_nist_time_changes_only_reviewed_server_and_keeps_polling_conservative():
    from provisioning.native_settings import nist_time_config

    original = b"# native configuration\r\ndriftfile /media/system-config/ntp.drift\r\nserver time.nest.com\r\nrestrict default nomodify noquery\r\n"
    assert nist_time_config(original) == original.replace(
        b"server time.nest.com", b"server time.nist.gov minpoll 6 maxpoll 10"
    )


@pytest.mark.parametrize(
    "bad",
    [
        b"server other.example\n",
        b"server time.nest.com iburst\n",
        b"server time.nest.com\nserver other.example\n",
        b"server time.nest.com\npool example.org\n",
        b"# server time.nest.com\n",
        b"server time.nest.com\n\x00",
    ],
)
def test_nist_time_refuses_ambiguous_or_changed_input(bad):
    from provisioning.native_settings import nist_time_config

    with pytest.raises(Invalid):
        nist_time_config(bad)
