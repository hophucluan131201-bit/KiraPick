"""Inventory of the packages a build hands to testers (checklist G1-G4): version, edition, commit, each file's size and
SHA-256, and the LIC-1 package check (scripts/check_package.py) on the very program folder those packages contain.

    python scripts/package_inventory.py --dist dist --edition directml|cuda|openvino --commit <sha> [--run <id>]
                                        [--installed <folder>] --out dist/package-inventory.json

``--dist``: the build output (``dist\\KiraPick`` = program folder, ``dist\\installer`` = what is handed out).
``--installed``: optionally the folder the installer really installed (silent install on the CI runner), checked too.
Writes the JSON and a Markdown table next to it (``.md``) to paste into the tester sheet. No network, no photos.
Exit 1 when a package check fails, except cuDNN DLLs left by an UPGRADE from 3.0.0a in ``--installed`` (CLEAN-2 is
an open owner decision: reported, not failed).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import check_package  # noqa: E402


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _cudnn_only(failures: list[str]) -> bool:
    return bool(failures) and all("cuDNN must not be shipped" in f for f in failures)


def inventory(dist: Path, edition: str, commit: str, run: str | None = None, installed: Path | None = None,
              upgrade_from: str | None = None, policy=None) -> dict:  # noqa: ANN001
    from app import __version__
    from app.edition import version_for

    files = sorted(p for p in (dist / "installer").rglob("*") if p.is_file()) if (dist / "installer").is_dir() else []
    out: dict = {
        "version": version_for(__version__, edition), "edition": edition, "commit": commit, "run": run,
        "packages": [{"file": p.relative_to(dist / "installer").as_posix(), "bytes": p.stat().st_size,
                      "sha256": sha256(p)} for p in files],
        "program_folder": check_package.check(dist / "KiraPick", edition, policy),
    }
    out["ok"] = out["program_folder"]["ok"]
    if installed is not None:
        report = check_package.check(installed, edition, policy)
        clean2 = upgrade_from is not None and edition == "cuda" and _cudnn_only(report["failures"])
        out["installed"] = {"folder": installed.name, "upgrade_from": upgrade_from, "check": report,
                            "clean2_leftover": [f.split(":")[0].removeprefix("P3 ") for f in report["failures"]]
                            if clean2 else []}
        out["ok"] = out["ok"] and (report["ok"] or clean2)
    return out


def markdown(inv: dict) -> str:
    rows = [f"| `{p['file']}` | {p['bytes']:,} | `{p['sha256']}` |".replace(",", " ") for p in inv["packages"]]
    pf = inv["program_folder"]
    lines = [f"## Gói {inv['edition']} — KiraPick {inv['version']}", "",
             f"- Commit: `{inv['commit']}`" + (f" · run {inv['run']}" if inv.get("run") else ""),
             f"- Kiểm gói (P1–P4) trên thư mục chương trình: **{'đạt' if pf['ok'] else 'KHÔNG ĐẠT'}**, "
             f"{len(pf['models'])} trọng số" + "".join(f"\n  - {f}" for f in pf["failures"]), ""]
    if "installed" in inv:
        ins = inv["installed"]
        how = f"nâng cấp từ {ins['upgrade_from']}" if ins["upgrade_from"] else "cài mới"
        lines.append(f"- Kiểm trên thư mục đã cài ({how}): **{'đạt' if ins['check']['ok'] else 'KHÔNG ĐẠT'}**"
                     + (f"; còn {len(ins['clean2_leftover'])} DLL cuDNN do bản cũ cài (CLEAN-2, chờ quyết định)"
                        if ins["clean2_leftover"] else ""))
        lines.append("")
    lines += ["| File | Byte | SHA-256 |", "|---|---|---|", *rows, ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", type=Path, required=True)
    ap.add_argument("--edition", choices=("directml", "cuda", "openvino"), required=True)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--run")
    ap.add_argument("--installed", type=Path)
    ap.add_argument("--upgrade-from")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    inv = inventory(args.dist, args.edition, args.commit, args.run, args.installed, args.upgrade_from)
    args.out.write_text(json.dumps(inv, indent=1, ensure_ascii=False), encoding="utf-8")
    args.out.with_suffix(".md").write_text(markdown(inv), encoding="utf-8")
    print(markdown(inv))
    return 0 if inv["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
