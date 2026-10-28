"""CLIP ViT-L/14 (OpenAI) image embedding, LAION aesthetic score and style prompts.

- The embedding (768 numbers) describes content, light and style; it is stored per photo and
  feeds the personal taste model.
- LAION "improved aesthetic predictor" (sac+logos+ava1-l14-linearMSE, Apache-2.0) reads the
  L2-normalised embedding and gives a 1..10 score of how much people like the photo on average.
- Style prompts: CLIP text embeddings of fixed English prompts, computed at build time; a photo
  whose similarity passes a prompt's threshold gets that tag (e.g. intentional motion blur), which
  explains the taste and lets artistic photos escape the technical penalties.

Preprocessing is exactly CLIP's (shorter side 224 bicubic, centre crop 224, CLIP mean/std), so
the scores mean what LAION trained them to mean. OpenAI's model card calls deployed use out of
scope; the owner accepted that for this non-commercial app (README disclaimer).
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from app.ai.clip_version import CLIP_VERSION
from app.ai.models import ModelRegistry, ModelUnavailableError
from app.ai.runtime import create_session

__all__ = ["ARTISTIC_TAGS", "CLIP_VERSION", "ClipAesthetic", "preprocess"]

SIZE = 224
MEAN = (0.48145466, 0.4578275, 0.40821073)
STD = (0.26862954, 0.26130258, 0.27577711)
# Tags that mean "this softness/darkness is a choice": they may lift the technical cap (spec §4).
ARTISTIC_TAGS = frozenset({"motion_blur_intentional", "low_key", "silhouette", "soft_dreamy", "backlit_flare",
                           "long_exposure", "film_grain"})


def preprocess(bgr: np.ndarray) -> np.ndarray:
    rgb = Image.fromarray(np.ascontiguousarray(bgr[:, :, ::-1]))
    w, h = rgb.size
    # torchvision Resize(224): shorter side 224, longer side int(224 * long / short) (truncated)
    nw, nh = (SIZE, int(SIZE * h / w)) if w <= h else (int(SIZE * w / h), SIZE)
    rgb = rgb.resize((nw, nh), Image.Resampling.BICUBIC)
    left, top = int(round((nw - SIZE) / 2.0)), int(round((nh - SIZE) / 2.0))
    crop = np.asarray(rgb.crop((left, top, left + SIZE, top + SIZE)), np.float32) / 255.0
    x = (crop - np.array(MEAN, np.float32)) / np.array(STD, np.float32)
    return x.transpose(2, 0, 1)[None].astype(np.float32)


class ClipAesthetic:
    def __init__(self, registry: ModelRegistry, *, prefer_gpu: bool = True) -> None:
        self.session = create_session(registry.require("clip_l14_image"), prefer_gpu=prefer_gpu)
        self._input = self.session.session.get_inputs()[0].name
        self.head = create_session(registry.require("laion_aesthetic"), prefer_gpu=False)  # tiny
        self._head_input = self.head.session.get_inputs()[0].name
        self.device = self.session.device
        self.check: dict = {"device": self.device, "note": self.session.fallback_reason}
        self._prompt_ids: list[str] = []
        self._prompts = np.zeros((0, 768), np.float32)
        self._thresholds = np.zeros(0, np.float32)
        self._negatives: np.ndarray | None = None
        try:
            with np.load(registry.require("clip_prompts")) as data:
                self._prompt_ids = [str(i) for i in data["ids"]]
                vecs = data["vectors"].astype(np.float32)
                self._prompts = vecs / np.linalg.norm(vecs, axis=1, keepdims=True)
                self._thresholds = data["thresholds"].astype(np.float32)
                if "negatives" in data.files:  # neutral counterpart prompts: tag on the margin over them
                    neg = data["negatives"].astype(np.float32)
                    self._negatives = neg / np.linalg.norm(neg, axis=1, keepdims=True)
        except ModelUnavailableError:
            self.check["prompts"] = "missing"

    def embed(self, bgr: np.ndarray) -> np.ndarray:
        out = self.session.run(None, {self._input: preprocess(bgr)})[0].reshape(-1).astype(np.float32)
        self.device = self.session.device  # a GPU error moves it to the CPU
        return out / max(float(np.linalg.norm(out)), 1e-12)

    def laion(self, emb: np.ndarray) -> float:
        out = self.head.run(None, {self._head_input: emb.reshape(1, -1).astype(np.float32)})[0]
        return round(float(out.reshape(-1)[0]), 4)

    def tags(self, emb: np.ndarray) -> list[tuple[str, float]]:
        if not self._prompt_ids:
            return []
        sims = self._prompts @ emb.astype(np.float32)
        if self._negatives is not None:
            sims = sims - self._negatives @ emb.astype(np.float32)
        hits = [(self._prompt_ids[i], float(sims[i])) for i in range(len(sims)) if sims[i] >= self._thresholds[i]]
        return sorted(hits, key=lambda t: -t[1])

    def prompt_vectors(self) -> dict[str, np.ndarray]:
        """Prompt id -> unit text embedding (to explain what the taste model learnt)."""
        return dict(zip(self._prompt_ids, self._prompts, strict=True))


STYLE_LABELS = {  # prompt id -> Vietnamese words for explanations
    "motion_blur_intentional": "cố ý rung mờ", "low_key": "tối kiểu low-key", "silhouette": "bóng đen ngược sáng",
    "soft_dreamy": "mềm mơ màng", "backlit_flare": "ngược sáng", "long_exposure": "phơi sáng lâu",
    "film_grain": "hạt kiểu film", "close_up": "cận mặt", "full_body": "toàn thân", "smiling": "cười",
    "eyes_closed": "nhắm mắt", "bokeh": "xoá phông", "golden_hour": "nắng vàng", "night": "ban đêm",
    "studio": "phông studio", "greenery": "cây lá", "urban": "đường phố", "dynamic_pose": "dáng chuyển động",
    "looking_at_camera": "nhìn thẳng máy", "water": "hồ bơi / nước", "vivid_colour": "màu rực",
    "black_white": "đen trắng",
}
