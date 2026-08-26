"""Pipeline desacoplado para validar imagens sem persistir frames por padrão."""

import hashlib
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from app.config import settings
from ml.detector import Deteccao, detectar_imagem, detectar_imagem_real, status_detector

ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}


@dataclass
class FrameDetection:
    classe_id: int
    nome: str
    confianca: float
    severidade: str
    tipo: str
    bbox: tuple[int, int, int, int]
    classe_modelo: str | None = None
    duplicada: bool = False


@dataclass
class FrameResult:
    frame_id: str
    deteccoes: list[FrameDetection]
    timestamp: str
    latencia_ms: int
    relevante: bool
    modo: str


class VisualValidationService:
    def __init__(self, detector: Callable[[str, float], list[Deteccao]] | None = None, now: Callable[[], float] = time.monotonic) -> None:
        self._detector = detector or detectar_imagem_real
        self._now = now
        self._recent: dict[str, float] = {}

    def validate_frame(self, content: bytes, mime_type: str, frame_id: str, threshold: float | None = None) -> FrameResult:
        if mime_type not in ALLOWED_IMAGE_MIME:
            raise ValueError("Formato inválido. Use JPEG, PNG ou WEBP.")
        if not content:
            raise ValueError("Frame vazio.")
        if len(content) > settings.yolo_max_frame_bytes:
            raise ValueError("Frame ultrapassa o limite configurado.")
        threshold = settings.yolo_threshold if threshold is None else threshold
        if not 0.05 <= threshold <= 0.95:
            raise ValueError("Threshold deve estar entre 0,05 e 0,95.")

        start = self._now()
        suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime_type]
        path = ""
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as file:
                file.write(content)
                path = file.name
            raw = self._detector(path, threshold)
        finally:
            if path:
                Path(path).unlink(missing_ok=True)

        now = self._now()
        detections: list[FrameDetection] = []
        for item in raw:
            key = hashlib.sha256((item.nome + ":" + str(item.bbox)).encode()).hexdigest()
            duplicate = now - self._recent.get(key, -10_000) < settings.yolo_cooldown_seconds
            if not duplicate:
                self._recent[key] = now
            detections.append(FrameDetection(**asdict(item), duplicada=duplicate))
        mode = status_detector()["modo"]
        return FrameResult(frame_id=frame_id, deteccoes=detections, timestamp=datetime.now(UTC).isoformat(), latencia_ms=round((now - start) * 1000), relevante=any(not item.duplicada for item in detections), modo=mode)

    def simulate_frame(self, frame_id: str, threshold: float | None = None) -> FrameResult:
        threshold = settings.yolo_threshold if threshold is None else threshold
        start = self._now()
        raw = [item for item in detectar_imagem("simulacao", num_deteccoes=1) if item.confianca >= threshold]
        detections = [FrameDetection(**asdict(item)) for item in raw]
        return FrameResult(frame_id=frame_id, deteccoes=detections, timestamp=datetime.now(UTC).isoformat(), latencia_ms=round((self._now() - start) * 1000), relevante=bool(detections), modo="simulacao")


visual_validation_service = VisualValidationService()
