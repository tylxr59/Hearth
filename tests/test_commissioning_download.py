import pytest

from backend.validation import Invalid
from installer.download import download


@pytest.mark.parametrize(
    "origin",
    [
        "file:///etc/passwd",
        "https://user:pass@example.com",
        "http://example.com",
        "http://8.8.8.8",
        "https://example.com?secret=x",
        "https://example.com/path",
        "http://0.0.0.0",
        "http://169.254.169.254",
    ],
)
def test_bad_download_origin_never_opens_network(origin, tmp_path, monkeypatch):
    monkeypatch.setattr("urllib.request.build_opener", lambda *a: pytest.fail("network opened"))
    with pytest.raises(Invalid):
        download(origin, "token", tmp_path / "bundle.zip")
