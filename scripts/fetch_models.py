"""Download the pinned model weights (DEV/PACKAGING TIME ONLY — needs Internet).

    python scripts/fetch_models.py            # fetch missing/corrupt files
    python scripts/fetch_models.py --check    # only report
    python scripts/fetch_models.py --purpose identity,quality --dest build/models   # installer set

Every file is verified against the SHA-256 in configs/model-manifest.json; a
mismatch is deleted (only the .part file we wrote) and reported. The app
itself never downloads anything.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ai.models import ModelRegistry, ModelState, sha256_of  # noqa: E402


def main() -> int:
    for stream in (sys.stdout, sys.stderr):  # Vietnamese messages on cp1252 consoles
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report only, download nothing")
    parser.add_argument("--purpose", help="comma-separated purposes to fetch (default: all)")
    parser.add_argument("--dest", type=Path, help="folder for the weights (default: the app's models folder)")
    args = parser.parse_args()
    registry = ModelRegistry(args.dest)
    if args.purpose:
        wanted = set(args.purpose.split(","))
        registry.specs = {k: v for k, v in registry.specs.items() if v.purpose in wanted}
    registry.models_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for status in registry.all_status():
        spec = status.spec
        if status.state is ModelState.READY:
            print(f"OK       {spec.file}  ({spec.license})")
            continue
        if args.check:
            print(f"{status.state.value.upper():8} {spec.file}")
            failures += 1
            continue
        part = status.path.with_suffix(status.path.suffix + ".part")
        if spec.url.startswith("repo:"):  # converted by us, kept in the repository (see its provenance)
            src = Path(__file__).resolve().parents[1] / spec.url[len("repo:"):]
            print(f"Chép {spec.file} từ {src.parent.name}/ …", flush=True)
            try:
                part.write_bytes(src.read_bytes())
            except OSError as exc:
                print(f"  LỖI: {exc}")
                failures += 1
                continue
        else:
            print(f"Đang tải {spec.file} ({spec.size / 1e6:.0f} MB) …", flush=True)
            try:
                with urllib.request.urlopen(spec.url, timeout=120) as resp, open(part, "wb") as out:  # noqa: S310
                    while chunk := resp.read(1 << 20):
                        out.write(chunk)
            except OSError as exc:
                part.unlink(missing_ok=True)
                print(f"  LỖI tải: {exc}")
                failures += 1
                continue
        if sha256_of(part) != spec.sha256:
            part.unlink()
            print("  LỖI: SHA-256 không khớp, đã bỏ file tải về")
            failures += 1
            continue
        part.replace(status.path)
        print(f"  OK  ({spec.license})")
    print("Xong." if not failures else f"{failures} mô hình chưa sẵn sàng.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
