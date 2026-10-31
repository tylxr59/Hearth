import ssl

import pytest

from backend.mqtt import tls_context
from backend.validation import Invalid


def test_legacy_format_keeps_peer_identity_verification(monkeypatch):
    original = ssl.create_default_context
    contexts = []

    def context(*, cafile):
        assert cafile == "/trusted/mqtt-ca.pem"
        result = original()
        contexts.append(result)
        return result

    monkeypatch.setattr(ssl, "create_default_context", context)
    strict = tls_context({"ca": "/trusted/mqtt-ca.pem"})
    compatible = tls_context({"ca": "/trusted/mqtt-ca.pem", "legacy_certificate_format": True})
    assert strict.verify_flags & ssl.VERIFY_X509_STRICT
    assert not compatible.verify_flags & ssl.VERIFY_X509_STRICT
    assert compatible.verify_flags == strict.verify_flags & ~ssl.VERIFY_X509_STRICT
    for result in contexts:
        assert result.verify_mode == ssl.CERT_REQUIRED
        assert result.check_hostname is True
        assert result.minimum_version == ssl.TLSVersion.TLSv1_2


@pytest.mark.parametrize("value", [1, "true", None, [], {}])
def test_legacy_format_requires_explicit_boolean(value):
    with pytest.raises(Invalid, match="boolean"):
        tls_context({"legacy_certificate_format": value})


def test_legacy_format_requires_explicit_trust_anchor():
    with pytest.raises(Invalid, match="explicit trusted CA"):
        tls_context({"legacy_certificate_format": True})
