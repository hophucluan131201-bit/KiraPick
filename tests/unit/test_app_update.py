"""⚙ Cập nhật KiraPick: newest release of this edition from GitHub, SHA-256 checked, nothing else sent."""

from __future__ import annotations

import ast
import hashlib
import zipfile
from pathlib import Path

import pytest

from app.updates.app_update import UpdateError, download, newest_release, should_auto_check

ROOT = Path(__file__).resolve().parents[2]


def _asset(name: str, data: bytes = b"x") -> dict:
    return {"name": name, "size": len(data), "browser_download_url": f"https://github.com/r/{name}",
            "digest": "sha256:" + hashlib.sha256(data).hexdigest()}


RELEASES = [
    {"tag_name": "v2.2.0a", "prerelease": True, "draft": False, "assets": [_asset("KiraPick-Setup-2.2.0a.exe")]},
    {"tag_name": "v2.2.1", "prerelease": False, "draft": False, "assets": [_asset("KiraPick-2.2.1-BoCai.zip")]},
    {"tag_name": "v2.2.2b1", "prerelease": True, "draft": False, "assets": [_asset("KiraPick-2.2.2b1-BoCai.zip")]},
    {"tag_name": "v2.1.0b6", "prerelease": True, "draft": False, "assets": []},
    {"tag_name": "v2.3.0", "prerelease": False, "draft": True, "assets": []},  # drafts never count
]


def test_directml_gets_the_newest_official_release() -> None:
    r = newest_release(RELEASES, "directml", "2.2.0")
    assert r is not None and r.version == "2.2.1" and [a.name for a in r.assets] == ["KiraPick-2.2.1-BoCai.zip"]
    assert newest_release(RELEASES, "directml", "2.2.1") is None  # already the newest


def test_cuda_gets_the_newest_cuda_release() -> None:
    r = newest_release(RELEASES, "cuda", "2.1.0a")
    assert r is not None and r.version == "2.2.0a"
    assert newest_release(RELEASES, "cuda", "2.2.0a") is None


def _fetcher(blobs: dict[str, bytes]):  # noqa: ANN202
    def fetch(url: str, dest: Path, progress) -> None:  # noqa: ANN001
        dest.write_bytes(blobs[url.rsplit("/", 1)[-1]])
    return fetch


def test_download_checks_every_file_and_unpacks_the_installer(tmp_path: Path) -> None:
    exe, binary = b"setup-program", b"setup-data"
    bundle = tmp_path / "src.zip"
    with zipfile.ZipFile(bundle, "w") as zf:
        zf.writestr("KiraPick-Setup-2.2.1.exe", exe)
        zf.writestr("KiraPick-Setup-2.2.1-1.bin", binary)
    data = bundle.read_bytes()
    release = newest_release([{"tag_name": "v2.2.1", "prerelease": False, "draft": False,
                               "assets": [_asset("KiraPick-2.2.1-BoCai.zip", data)]}], "directml", "2.2.0")
    setup = download(release, _fetcher({"KiraPick-2.2.1-BoCai.zip": data}), lambda *_: None, tmp_path / "dl")
    assert setup.name == "KiraPick-Setup-2.2.1.exe" and setup.read_bytes() == exe
    assert (setup.parent / "KiraPick-Setup-2.2.1-1.bin").read_bytes() == binary


def test_a_file_that_does_not_match_its_digest_is_refused(tmp_path: Path) -> None:
    release = newest_release(RELEASES, "cuda", "2.1.0a")
    with pytest.raises(UpdateError):
        download(release, _fetcher({"KiraPick-Setup-2.2.0a.exe": b"tampered"}), lambda *_: None, tmp_path / "dl")
    assert not any((tmp_path / "dl").rglob("*.exe"))


def test_assets_without_a_published_digest_are_refused(tmp_path: Path) -> None:
    rel = [{"tag_name": "v2.2.1", "prerelease": False, "draft": False,
            "assets": [{"name": "KiraPick-2.2.1-BoCai.zip", "size": 1, "browser_download_url": "https://x/y"}]}]
    release = newest_release(rel, "directml", "2.2.0")
    with pytest.raises(UpdateError):
        download(release, _fetcher({}), lambda *_: None, tmp_path / "dl")


def test_auto_check_off_by_default_and_daily() -> None:
    assert not should_auto_check(enabled=False, last_check=None, today="2026-10-28")
    assert should_auto_check(enabled=True, last_check="2026-10-27", today="2026-10-28")
    assert not should_auto_check(enabled=True, last_check="2026-10-28", today="2026-10-28")


def test_only_the_updater_may_use_the_network() -> None:
    allowed = {ROOT / "app" / "updates", ROOT / "app" / "selftest.py"}  # selftest only blocks sockets
    bad = []
    for path in (ROOT / "app").rglob("*.py"):
        if any(path == a or a in path.parents for a in allowed):
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            if any(n.split(".")[0] in {"urllib", "http", "socket", "ssl", "requests", "httpx"} for n in names):
                bad.append(f"{path.relative_to(ROOT)}: {names}")
    assert bad == []
