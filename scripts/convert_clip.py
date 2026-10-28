"""Build CLIP ViT-L/14 image ONNX, the LAION aesthetic head and the style prompts (BUILD TIME ONLY).

    .venv-convert\\Scripts\\pip install -r packaging\\requirements-convert.txt
    .venv-convert\\Scripts\\python scripts\\convert_clip.py --out build\\models

- OpenAI CLIP ViT-L/14 (Radford et al. 2021; code MIT; the model card calls deployed use out of
  scope — accepted by the owner for this non-commercial app, 2026-10-28). The checkpoint is
  downloaded from OpenAI and checked by the SHA-256 that is part of its URL; the image tower with its
  projection is exported with a static 1x3x224x224 input and checked against PyTorch.
- LAION improved aesthetic predictor sac+logos+ava1-l14-linearMSE (Apache-2.0), checked by MD5
  as published and by SHA-256; exported and checked.
- Style prompts: text embeddings of PROMPTS (positive and neutral counterpart), stored as npz.
Each output gets a ``.sha256`` sidecar for the model manifest (not byte-reproducible).
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import urllib.request
from pathlib import Path

CLIP_URL = ("https://openaipublic.azureedge.net/clip/models/"
            "b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836/ViT-L-14.pt")
CLIP_SHA256 = "b8cca3fd41ae0c99ba7e8951adf17d267cdb84cd88be6f7c2e0eca1737a03836"
HEAD_URL = ("https://raw.githubusercontent.com/christophschuhmann/improved-aesthetic-predictor/main/"
            "sac%2Blogos%2Bava1-l14-linearMSE.pth")
HEAD_NAME = "sac+logos+ava1-l14-linearMSE.pth"
HEAD_MD5 = "b1047fd767a00134b8fd6529bf19521a"
HEAD_SHA256 = "21dd590f3ccdc646f0d53120778b296013b096a035a2718c9cb0d511bff0f1e0"
CLIP_ONNX, HEAD_ONNX, PROMPTS_NPZ = "clip_l14_image.onnx", "laion_aesthetic.onnx", "clip_prompts_v1.npz"
PROMPT_MARGIN = 0.03  # tag when sim(positive) - sim(neutral) >= this (owner sample: 0.02 tagged "motion blur" on sharp photos)

# id, positive prompt, neutral counterpart. Artistic ids must match app.ai.clip_aesthetic.ARTISTIC_TAGS.
PROMPTS = (
    ("motion_blur_intentional", "a photo with intentional artistic motion blur", "a sharp photo"),
    ("low_key", "a dark low-key portrait with dramatic shadows", "a bright evenly lit photo"),
    ("silhouette", "a silhouette of a person against the light", "a front-lit photo of a person"),
    ("soft_dreamy", "a soft dreamy portrait with haze and glow", "a crisp clear photo"),
    ("backlit_flare", "a backlit photo with sun flare", "a photo without backlight"),
    ("long_exposure", "a long exposure photo with light trails", "a normal photo"),
    ("film_grain", "a grainy film photo", "a clean digital photo"),
    ("close_up", "a close-up portrait of a face", "a full-body photo of a person"),
    ("full_body", "a full-body photo of a person", "a close-up portrait of a face"),
    ("smiling", "a photo of a person smiling", "a photo of a person with a neutral expression"),
    ("eyes_closed", "a photo of a person with closed eyes", "a photo of a person with open eyes"),
    ("bokeh", "a portrait with a strongly blurred bokeh background", "a photo with everything in focus"),
    ("golden_hour", "a photo in warm golden hour sunlight", "a photo in neutral light"),
    ("night", "a photo taken at night", "a photo taken in daylight"),
    ("studio", "a studio photo with a plain backdrop", "a photo taken outdoors"),
    ("greenery", "a photo of a person among plants and greenery", "a photo of a person indoors"),
    ("urban", "a street photo in the city", "a photo in nature"),
    ("dynamic_pose", "a person in a dynamic action pose", "a person standing still"),
    ("looking_at_camera", "a person looking straight at the camera", "a person looking away from the camera"),
    ("water", "a photo at a swimming pool or by the water", "a photo on dry land"),
    ("vivid_colour", "a photo with vivid saturated colors", "a photo with muted colors"),
    ("black_white", "a black and white photo", "a color photo"),
)


def _digest(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with open(path, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _fetch(url: str, dest: Path) -> None:
    if not dest.is_file():
        print(f"Downloading {url}", flush=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)  # noqa: S310 - fixed https URL, checked below
        tmp.replace(dest)


def _sidecar(path: Path) -> None:
    path.with_name(path.name + ".sha256").write_text(f"{_digest(path)} {path.stat().st_size}\n")
    print(f"{path.name}: {path.stat().st_size / 1e6:.0f} MB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cache", type=Path, help="folder with already downloaded checkpoints")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    cache = args.cache or args.out
    clip_pt, head_pt = cache / "ViT-L-14.pt", cache / HEAD_NAME
    _fetch(CLIP_URL, clip_pt)
    _fetch(HEAD_URL, head_pt)
    if _digest(clip_pt) != CLIP_SHA256:
        print("CLIP checkpoint SHA-256 mismatch")
        return 1
    if _digest(head_pt, "md5") != HEAD_MD5 or _digest(head_pt) != HEAD_SHA256:
        print("LAION head checksum mismatch")
        return 1

    import numpy as np
    import onnx
    import onnxruntime as ort
    import open_clip
    import torch
    from open_clip.openai import load_openai_model

    model = load_openai_model(str(clip_pt), precision="fp32", device="cpu").eval()
    tokenizer = open_clip.get_tokenizer("ViT-L-14")

    class Image(torch.nn.Module):
        def __init__(self, m: torch.nn.Module) -> None:
            super().__init__()
            self.m = m

        def forward(self, image: torch.Tensor) -> torch.Tensor:  # CLIP-normalised 1x3x224x224
            return self.m.encode_image(image)

    class Head(torch.nn.Module):  # the LAION MLP (dropout is a no-op in eval)
        def __init__(self) -> None:
            super().__init__()
            self.layers = torch.nn.Sequential(
                torch.nn.Linear(768, 1024), torch.nn.Dropout(0.2), torch.nn.Linear(1024, 128), torch.nn.Dropout(0.2),
                torch.nn.Linear(128, 64), torch.nn.Dropout(0.1), torch.nn.Linear(64, 16), torch.nn.Linear(16, 1))

        def forward(self, emb: torch.Tensor) -> torch.Tensor:
            return self.layers(emb)

    head = Head()
    head.load_state_dict(torch.load(head_pt, map_location="cpu", weights_only=True))
    head.eval()
    image = Image(model).eval()

    def export(module: torch.nn.Module, example: torch.Tensor, target: Path, inp: str, out: str) -> None:
        tmp = target.with_suffix(".tmp.onnx")
        torch.onnx.export(module, (example,), str(tmp), input_names=[inp], output_names=[out], opset_version=18,
                          dynamo=True)
        onnx.save(onnx.load(str(tmp), load_external_data=True), str(target), save_as_external_data=False)
        tmp.unlink()
        Path(str(tmp) + ".data").unlink(missing_ok=True)

    clip_onnx, head_onnx = args.out / CLIP_ONNX, args.out / HEAD_ONNX
    export(image, torch.zeros(1, 3, 224, 224), clip_onnx, "image", "embedding")
    export(head, torch.zeros(1, 768), head_onnx, "emb", "score")

    rng = np.random.default_rng(0)
    cs = ort.InferenceSession(str(clip_onnx), providers=["CPUExecutionProvider"])
    hs = ort.InferenceSession(str(head_onnx), providers=["CPUExecutionProvider"])
    for _ in range(4):
        x = rng.normal(0, 1, (1, 3, 224, 224)).astype(np.float32)
        with torch.no_grad():
            ref = image(torch.from_numpy(x)).numpy().reshape(-1)
        got = cs.run(None, {"image": x})[0].reshape(-1)
        cos = float(ref @ got / (np.linalg.norm(ref) * np.linalg.norm(got)))
        unit = (ref / np.linalg.norm(ref)).astype(np.float32).reshape(1, -1)
        with torch.no_grad():
            h_ref = float(head(torch.from_numpy(unit)).reshape(-1)[0])
        h_got = float(hs.run(None, {"emb": unit})[0].reshape(-1)[0])
        print(f"embedding cosine {cos:.6f}; LAION torch {h_ref:.4f} onnx {h_got:.4f}")
        if cos < 0.999 or abs(h_ref - h_got) > 0.01:
            print("ONNX output differs from PyTorch")
            return 1

    with torch.no_grad():
        def text(prompts: list[str]) -> np.ndarray:
            t = model.encode_text(tokenizer(prompts)).float()
            return (t / t.norm(dim=-1, keepdim=True)).numpy()
        pos = text([p for _, p, _ in PROMPTS])
        neg = text([n for _, _, n in PROMPTS])
    np.savez(args.out / PROMPTS_NPZ, ids=np.array([i for i, _, _ in PROMPTS]),
             texts=np.array([p for _, p, _ in PROMPTS]), vectors=pos.astype(np.float32),
             negatives=neg.astype(np.float32), thresholds=np.full(len(PROMPTS), PROMPT_MARGIN, np.float32))
    for path in (clip_onnx, head_onnx, args.out / PROMPTS_NPZ):
        _sidecar(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
