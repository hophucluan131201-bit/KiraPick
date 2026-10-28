"""⚙ Cập nhật KiraPick: download the newest installer of this edition from KiraPick's GitHub releases.

Only runs when the user clicks it (or once a day if they switched the check on; off by default).
It reads the public release list, downloads the installer files over HTTPS and checks each one
against the SHA-256 digest GitHub publishes for it; then the installer is started and the app
closes. Nothing about the user, their photos or their scores is sent.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

REPO = "hophucluan131201-bit/KiraPick"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
TIMEOUT_S = 60
HOSTS = ("api.github.com", "github.com", "release-assets.githubusercontent.com")
# edition -> version pattern of its releases: official DirectML "2.2.1", CUDA "2.2.0a", OpenVINO "2.2.0b"
_PATTERNS = {"directml": r"\d+\.\d+\.\d+", "cuda": r"\d+\.\d+\.\d+a", "openvino": r"\d+\.\d+\.\d+b"}

Progress = Callable[[int, int], None]
Fetch = Callable[[str, Path, Progress], None]


class UpdateError(RuntimeError):
    """Plain-language reason why no update was installed (nothing was changed)."""


@dataclass(frozen=True, slots=True)
class Asset:
    name: str
    size: int
    url: str
    sha256: str | None


@dataclass(frozen=True, slots=True)
class Release:
    version: str
    assets: list[Asset]

    @property
    def size(self) -> int:
        return sum(a.size for a in self.assets)


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3])


def _installer_assets(assets: list[Asset]) -> list[Asset]:
    zips = [a for a in assets if a.name.endswith("-BoCai.zip")]
    if zips:
        return zips[:1]
    return [a for a in assets if a.name.lower().endswith((".exe", ".bin"))]


def newest_release(releases: list[dict], edition: str, current: str) -> Release | None:
    """The newest release of ``edition`` that is newer than ``current``, or None."""
    pattern = re.compile(rf"v?({_PATTERNS[edition]})")
    best: Release | None = None
    for r in releases:
        m = pattern.fullmatch(str(r.get("tag_name", "")))
        if r.get("draft") or m is None:
            continue
        if edition == "directml" and r.get("prerelease"):
            continue
        version = m.group(1)
        if _numbers(version) <= _numbers(current) or (best and _numbers(version) <= _numbers(best.version)):
            continue
        assets = [Asset(str(a["name"]), int(a.get("size", 0)), str(a["browser_download_url"]),
                        str(a["digest"]).split(":", 1)[1].lower() if str(a.get("digest", "")).startswith("sha256:")
                        else None) for a in r.get("assets", [])]
        wanted = _installer_assets(assets)
        if wanted:
            best = Release(version, wanted)
    return best


def should_auto_check(*, enabled: bool, last_check: str | None, today: str) -> bool:
    return enabled and last_check != today


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def download(release: Release, fetch: Fetch, progress: Progress, folder: Path) -> Path:
    """Download and check every installer file into ``folder``; returns the Setup.exe to run."""
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    try:
        for asset in release.assets:
            if not asset.sha256:
                raise UpdateError(f"{asset.name}: GitHub không công bố mã SHA-256 nên không cài (an toàn)")
            part = folder / (asset.name + ".part")
            try:
                fetch(asset.url, part, progress)
            except OSError as exc:
                raise UpdateError(f"tải {asset.name} thất bại ({type(exc).__name__})") from exc
            if (asset.size and part.stat().st_size != asset.size) or _sha256(part) != asset.sha256:
                raise UpdateError(f"{asset.name}: tải về không khớp mã kiểm tra (SHA-256) — đã bỏ")
            target = folder / asset.name
            part.replace(target)
            if target.suffix == ".zip":
                with zipfile.ZipFile(target) as zf:
                    for name in zf.namelist():
                        base = Path(name).name
                        if base.lower().endswith((".exe", ".bin")):
                            with zf.open(name) as src, open(folder / base, "wb") as out:
                                shutil.copyfileobj(src, out, 1 << 20)
                target.unlink()
        setups = sorted(folder.glob("KiraPick-Setup-*.exe"))
        if not setups:
            raise UpdateError("bản tải về không có bộ cài")
        return setups[0]
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise


def fetch_url(url: str, dest: Path, progress: Progress) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "KiraPick-update"})  # no personal data
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp, open(dest, "wb") as out:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while chunk := resp.read(1 << 20):
            out.write(chunk)
            done += len(chunk)
            progress(done, total)


def list_releases() -> list[dict]:
    req = urllib.request.Request(RELEASES_URL, headers={"User-Agent": "KiraPick-update",
                                                        "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed https URL
            return json.loads(resp.read(5 << 20))
    except (OSError, ValueError) as exc:
        raise UpdateError(f"không kết nối được GitHub ({type(exc).__name__})") from exc


def start_installer(setup: Path) -> None:
    """Run the downloaded installer (it replaces this copy of KiraPick; data and learning stay)."""
    if sys.platform != "win32":
        raise UpdateError("chỉ cập nhật được trên Windows")
    subprocess.Popen([str(setup)], cwd=str(setup.parent), close_fds=True)  # noqa: S603 - our checked installer
