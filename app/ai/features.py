"""What each KiraPick function runs on (a model weight or a plain rule), and what happens when the weight is off.

Work screens name functions only ("Gom ảnh theo người", "Hợp gu"…). Model names, files, licences and the status in
this build are shown in one place: ⚙ Tuỳ chọn → ℹ Giới thiệu → Mô hình và giấy phép (app.ui.about_models), built
from this table, configs/model-policy.json and configs/model-manifest.json.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.models import ModelRegistry, ModelState


@dataclass(frozen=True, slots=True)
class Feature:
    name: str  # the function, as the work screens say it
    modes: str  # "Chụp cá nhân", "Media", or both
    models: tuple[str, ...]  # model ids (configs/model-manifest.json); empty = a rule, no model
    rule: str = ""  # what it runs on when it needs no model
    without: str = ""  # what the user gets when the model is off or missing


FEATURES: tuple[Feature, ...] = (
    Feature("Dò người trong ảnh", "Chụp cá nhân, Media", ("person_detector_s", "person_detector_m"),
            without="Không dò được người: không gom tay theo người được, Media không xếp cỡ cảnh. Duyệt, P/X, sao, "
                    "xuất vẫn dùng được."),
    Feature("Dò khuôn mặt", "Chụp cá nhân, Media", ("face_detector",),
            without="Không đo nét ở mặt / mắt; Media xếp cỡ cảnh chỉ theo khung người."),
    Feature("Chấm chất lượng khuôn mặt", "Chụp cá nhân", ("face_quality",),
            without="Điểm kỹ thuật bỏ phần khuôn mặt, phần còn lại chia lại tỉ lệ."),
    Feature("Mắt nhắm, biểu cảm", "Chụp cá nhân", ("face_mesh", "face_blendshapes"),
            without="Không cảnh báo mắt nhắm."),
    Feature("Gom ảnh theo người tự động", "Chụp cá nhân, Media", ("face_embedder",),
            without="Gom tay: chuột phải trên ảnh → ➕ Tạo chủ thể mới / Gán cho chủ thể…; Gộp, Tách, Đổi tên, "
                    "Hoàn tác như 3.0.0. Ảnh không có người được dò thì không gom được (app báo lý do)."),
    Feature("Hợp gu, dạy gu", "Chụp cá nhân", ("clip_l14_image", "clip_prompts", "laion_aesthetic"),
            without="Điểm xếp hạng chỉ có phần Kỹ thuật; 🎓 Dạy gu chưa dùng được."),
    Feature("Gợi ý nội dung, đổi cảnh, gợi ý booth", "Media", ("clip_l14_image", "clip_prompts"),
            without="Nội dung gán tay (Alt+1–5, nhiều ảnh một lúc); khoảnh khắc chia theo khoảng nghỉ; tên booth "
                    "gợi ý theo khoảnh khắc."),
    Feature("Gom theo dáng người / trang phục bằng AI (bản 3.0.0)", "—", ("body_reid",),
            without="Không dùng trong bản này; gom tay như trên."),
    Feature("Nhận mặt mạnh (bản 3.0.0)", "—", ("face_embedder_arcface",),
            without="Đã gỡ (điều khoản không cho dùng thương mại); gom tay như trên."),
    Feature("Điểm thẩm mỹ và kỹ thuật bằng AI (bản 3.0.0)", "—", ("aesthetic", "tech_iqa", "face_iqa"),
            without="Đã gỡ (điều khoản không cho dùng thương mại); độ nét đo bằng quy tắc trên ảnh gốc."),
    Feature("Độ nét (đo trên ảnh gốc), lỗi nét Q / W / R", "Chụp cá nhân, Media", (),
            rule="Quy tắc đo độ nét trên vùng ảnh gốc 100 %, không cần mô hình"),
    Feature("Chia khoảnh khắc, giờ máy ảnh, nguồn máy", "Media", (),
            rule="Quy tắc theo giờ chụp đã chỉnh và khoảng nghỉ ≥ 5 phút, không cần mô hình"),
    Feature("Cỡ cảnh Toàn / Trung / Cận", "Media", (),
            rule="Quy tắc trên khung người và khuôn mặt đã dò (cần hai chức năng dò ở trên)"),
)

STATUS_TEXT = {
    "verified": "Đang dùng",
    "pending": "Tắt: chờ xác minh quyền sử dụng",
    "never": "Không dùng: điều khoản không cho phép",
}


@dataclass(frozen=True, slots=True)
class ModelRow:
    model_id: str
    name: str
    file: str
    sha256: str
    source: str
    licence: str
    status: str  # STATUS_TEXT, plus "thiếu file" when allowed but not installed
    terms: str


def model_rows(registry: ModelRegistry | None = None) -> list[ModelRow]:
    """Every weight KiraPick knows, with its status in this build (allowed and installed / off / never)."""
    registry = registry or ModelRegistry()
    rows = []
    for model_id, spec in registry.specs.items():
        entry = registry.policy.entry(model_id)
        status = STATUS_TEXT.get(entry.status if entry else "", "Không dùng: không có trong danh sách cho phép")
        if entry is not None and entry.verified:
            state = registry.status(model_id).state
            if state is ModelState.MISSING:
                status = "Được phép, chưa cài file này"
            elif state is not ModelState.READY:
                status = "Được phép, file không đúng bản đã kiểm"
        pinned = entry.pinned[0].sha256 if entry is not None and entry.pinned else spec.sha256
        rows.append(ModelRow(model_id, spec.name, spec.file, pinned, spec.url, spec.license, status,
                             entry.terms if entry else ""))
    return rows


def feature_status(feature: Feature, rows: dict[str, ModelRow]) -> str:
    if not feature.models:
        return "Đang dùng (quy tắc)"
    states = [rows[m].status for m in feature.models if m in rows]
    if any(s == "Đang dùng" for s in states):
        return "Đang dùng"
    return states[0] if states else "Không dùng"
