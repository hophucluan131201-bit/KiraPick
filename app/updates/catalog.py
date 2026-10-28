"""Signed catalogue of curated model updates (Ed25519 over the exact JSON bytes)."""

from __future__ import annotations

import base64
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from app.ai.models import ModelRegistry

REPO = "hophucluan131201-bit/KiraPick"
CATALOG_URL = f"https://github.com/{REPO}/releases/download/models-catalog/models-catalog.json"
SIGNATURE_URL = CATALOG_URL + ".sig"
HOSTS = ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
TIMEOUT_S = 60
_KEY_FILE = Path(__file__).resolve().parents[2] / "configs" / "update-public-key.txt"


class CatalogError(RuntimeError):
    """The catalogue is missing, not signed by KiraPick, or malformed."""


@dataclass(frozen=True, slots=True)
class Entry:
    id: str
    version: str
    file: str
    url: str
    size: int
    sha256: str
    license: str
    min_app: str
    embedding_compatible: bool
    notes: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> Entry:
        try:
            return cls(str(d["id"]), str(d["version"]), Path(str(d["file"])).name, str(d["url"]), int(d["size"]),
                       str(d["sha256"]).lower(), str(d["license"]), str(d.get("min_app", "0")),
                       bool(d.get("embedding_compatible", True)), str(d.get("notes", "")))
        except (KeyError, TypeError, ValueError) as exc:
            raise CatalogError(f"malformed catalogue entry: {exc}") from exc


def public_key() -> bytes:
    return base64.b64decode(_KEY_FILE.read_text(encoding="ascii").strip())


def verify_catalog(data: bytes, signature: bytes, key: bytes | None = None) -> dict:
    try:
        Ed25519PublicKey.from_public_bytes(key or public_key()).verify(signature, data)
    except (InvalidSignature, ValueError) as exc:
        raise CatalogError("chữ ký danh sách mô hình không hợp lệ") from exc
    try:
        catalog = json.loads(data)
    except ValueError as exc:
        raise CatalogError("danh sách mô hình hỏng") from exc
    if catalog.get("schema") != 1 or not isinstance(catalog.get("models"), list):
        raise CatalogError("danh sách mô hình không đúng định dạng")
    return catalog


def _version(v: str) -> tuple[int, ...]:
    out = []
    for part in v.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out)


def installed_version(registry: ModelRegistry, model_id: str) -> str:
    """Catalogue version of an updated model, or "bundled"."""
    return registry.override_version(model_id) or "bundled"


def pending_updates(catalog: dict, registry: ModelRegistry, app_version: str) -> list[Entry]:
    out = []
    for raw in catalog.get("models", []):
        e = Entry.from_dict(raw)
        if e.id not in registry.specs or _version(e.min_app) > _version(app_version):
            continue
        if installed_version(registry, e.id) != e.version:
            out.append(e)
    return out


def should_auto_check(*, enabled: bool, last_check: str | None, today: str) -> bool:
    return enabled and last_check != today


def _get(url: str, limit: int = 1 << 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "KiraPick-model-update"})  # no personal data
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:  # noqa: S310 - fixed https URL
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise CatalogError("danh sách mô hình quá lớn")
    return data


def download_catalog(get: Callable[[str], bytes] = _get) -> dict:
    try:
        data, sig = get(CATALOG_URL), get(SIGNATURE_URL)
    except OSError as exc:
        raise CatalogError(f"không kết nối được ({type(exc).__name__})") from exc
    return verify_catalog(data, sig)
