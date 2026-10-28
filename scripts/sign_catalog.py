"""Sign configs/models-catalog.json for the AI-model update (CI only; needs the private key).

    KIRAPICK_UPDATE_SIGNING_KEY=<base64 Ed25519 private key> python scripts/sign_catalog.py out_dir

Writes out_dir/models-catalog.json (exact bytes) and models-catalog.json.sig, and checks the
signature with the public key shipped in the app (configs/update-public-key.txt).
"""

from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.updates.catalog import Entry, verify_catalog  # noqa: E402


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    key = os.environ.get("KIRAPICK_UPDATE_SIGNING_KEY", "").strip()
    if not key:
        print("KIRAPICK_UPDATE_SIGNING_KEY is not set (GitHub: Settings → Secrets and variables → Actions)")
        return 1
    data = (ROOT / "configs" / "models-catalog.json").read_bytes()
    catalog = json.loads(data)
    for raw in catalog.get("models", []):
        Entry.from_dict(raw)  # malformed entries fail here, not on the users' PCs
    sig = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key)).sign(data)
    verify_catalog(data, sig)  # the app's public key accepts it
    (out / "models-catalog.json").write_bytes(data)
    (out / "models-catalog.json.sig").write_bytes(sig)
    print(f"signed {len(catalog.get('models', []))} model entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
