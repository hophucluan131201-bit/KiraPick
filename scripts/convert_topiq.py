"""Build models/weights/topiq_iaa_res50.onnx from the TOPIQ aesthetic checkpoint (BUILD/DEV TIME ONLY).

    python -m venv .venv-convert
    .venv-convert\\Scripts\\pip install -r packaging\\requirements-convert.txt
    .venv-convert\\Scripts\\pip install --no-deps pyiqa==0.1.14.1
    .venv-convert\\Scripts\\python scripts\\convert_topiq.py --out build\\models [--variant iaa|nr|face|all]

TOPIQ (Chen et al., IEEE TIP 2024) "CFANet" image aesthetics model with a ResNet50 backbone,
trained on AVA. Code and weights: IQA-PyTorch, PolyForm Noncommercial 1.0.0 (approved by the
owner for this non-commercial app, 2026-10-27). The checkpoint is downloaded from the
IQA-PyTorch GitHub release and checked by SHA-256; the ONNX output is checked against PyTorch
on several image shapes. The ONNX file is too large (280 MB) for the repository, so the build
converts it; its SHA-256 is written next to it for the packaged model manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import types
import urllib.request
from pathlib import Path

_HF = "https://huggingface.co/chaofengc/IQA-PyTorch-Weights/resolve/main/"
# variant -> checkpoint URL, its SHA-256, ONNX file, CFANet options, fixed (h, w) or None (any size)
VARIANTS = {
    "iaa": ("https://github.com/chaofengc/IQA-PyTorch/releases/download/v0.1-weights/cfanet_iaa_ava_res50-3cd62bb3.pth",
            "3cd62bb33f9933ed7c6e3d5e79129e81c898eba78b7a2af516a0b0b974616975", "topiq_iaa_res50.onnx",
            {"model_name": "cfanet_iaa_ava_res50", "inter_dim": 512, "num_heads": 8, "num_class": 10}, None),
    "nr": (_HF + "cfanet_nr_koniq_res50-9a73138b.pth",
           "9a73138beb3748dd6a83365610ac88fa1cd53225342c77fc9ed44a3be461354c", "topiq_nr_koniq_res50.onnx",
           {"model_name": "cfanet_nr_koniq_res50"}, None),
    "face": (_HF + "topiq_nr_cgfiqa_res50-0a8b8e4f.pth",
             "0a8b8e4f458c782301b9940e15699d2b5b8919252c973f52e7060d8070997898", "topiq_nr_face_res50.onnx",
             {"model_name": "topiq_nr_cgfiqa_res50", "align_crop_face": False}, (512, 512)),
}
CHECKPOINT_URL, CHECKPOINT_SHA256, ONNX_NAME = VARIANTS["iaa"][:3]
CHECK_SHAPES = ((384, 576), (576, 384), (384, 384), (384, 512))
TOLERANCE = 1e-3  # on the model's score scale (1..10 or 0..1)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True, help="folder for topiq_iaa_res50.onnx")
    parser.add_argument("--checkpoint", type=Path, help="already downloaded .pth (else downloaded; one variant)")
    parser.add_argument("--variant", choices=[*VARIANTS, "all"], default="iaa")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for variant in (VARIANTS if args.variant == "all" else [args.variant]):
        if (code := convert(variant, args.out, args.checkpoint)) != 0:
            return code
    return 0


def convert(variant: str, out: Path, checkpoint: Path | None) -> int:
    url, sha, onnx_name, options, fixed = VARIANTS[variant]
    ckpt = checkpoint or out / Path(url).name
    if not ckpt.is_file():
        print(f"Downloading {url}", flush=True)
        urllib.request.urlretrieve(url, ckpt)  # noqa: S310 - fixed https URL
    if _sha256(ckpt) != sha:
        print("Checkpoint SHA-256 mismatch")
        return 1

    for name in ("facexlib", "facexlib.utils", "facexlib.utils.face_restoration_helper"):
        sys.modules[name] = types.ModuleType(name)  # only TOPIQ's face variant needs facexlib
    sys.modules["facexlib.utils.face_restoration_helper"].FaceRestoreHelper = type(
        "FaceRestoreHelper", (), {"__init__": lambda self, *a, **k: None})  # KiraPick crops faces itself
    # Import only the TOPIQ architecture: pyiqa's package __init__ files pull in datasets, losses
    # and many more libraries. Empty packages pointing at the installed folders avoid that.
    import importlib.util

    if "pyiqa" not in sys.modules:  # once per process (--variant all converts several models)
        root = Path(importlib.util.find_spec("pyiqa").submodule_search_locations[0])
        for pkg, folder in (("pyiqa", root), ("pyiqa.archs", root / "archs"), ("pyiqa.utils", root / "utils")):
            module = types.ModuleType(pkg)
            module.__path__ = [str(folder)]
            sys.modules[pkg] = module
    import numpy as np
    import onnx
    import onnxruntime as ort
    import timm
    import torch

    create = timm.create_model

    def no_hub(*a, **k):  # noqa: ANN002, ANN003, ANN202 - the backbone comes from the checkpoint
        k["pretrained"] = False
        return create(*a, **k)

    timm.create_model = no_hub
    import pyiqa.archs.topiq_arch as topiq
    from pyiqa.archs.arch_util import dist_to_mos, load_pretrained_network

    topiq.timm.create_model = no_hub
    model = topiq.CFANet(semantic_model_name="resnet50", use_ref=False, test_img_size=None, pretrained=False,
                         **options)
    load_pretrained_network(model, str(ckpt), True, "params")
    model.eval()

    class Wrapper(torch.nn.Module):
        """RGB 0..1 image (sides multiples of 32) -> aesthetics: 10-bin distribution + mean 1..10;
        technical / face quality: one score 0..1."""

        def __init__(self, m: torch.nn.Module) -> None:
            super().__init__()
            self.m = m

        def forward(self, x: torch.Tensor):  # noqa: ANN201
            dist = self.m.forward_cross_attention(x)
            if dist.shape[-1] == 1:
                return dist
            return dist, dist_to_mos(dist)

    wrapper = Wrapper(model).eval()
    example = torch.rand(1, 3, *(fixed or (384, 576)))
    tmp = out / (onnx_name + ".tmp")
    names = ["dist", "mos"] if options.get("num_class", 1) > 1 else ["score"]
    dynamic = None
    if fixed is None:
        h, w = torch.export.Dim("h", min=192, max=1024), torch.export.Dim("w", min=192, max=1024)
        dynamic = {"x": {2: h, 3: w}}
    torch.onnx.export(wrapper, (example,), str(tmp), input_names=["image"], output_names=names,
                      dynamic_shapes=dynamic, opset_version=18, dynamo=True)
    target = out / onnx_name
    onnx.save(onnx.load(str(tmp), load_external_data=True), str(target), save_as_external_data=False)
    tmp.unlink()
    Path(str(tmp) + ".data").unlink(missing_ok=True)

    session = ort.InferenceSession(str(target), providers=["CPUExecutionProvider"])
    rng = np.random.default_rng(0)
    for shape in ([fixed] if fixed else CHECK_SHAPES):
        x = rng.random((1, 3, *shape), dtype=np.float32)
        with torch.no_grad():
            res = wrapper(torch.from_numpy(x))
            ref = float((res[1] if isinstance(res, tuple) else res).reshape(-1)[0])
        got = float(session.run(None, {"image": x})[-1].reshape(-1)[0])
        print(f"{shape}: torch {ref:.4f} onnx {got:.4f}")
        if abs(ref - got) > TOLERANCE:
            print("ONNX output differs from PyTorch")
            return 1
    digest = _sha256(target)
    (out / (onnx_name + ".sha256")).write_text(f"{digest} {target.stat().st_size}\n")
    print(f"{onnx_name}: {target.stat().st_size} bytes, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
