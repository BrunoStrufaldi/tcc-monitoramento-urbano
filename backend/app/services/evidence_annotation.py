"""Gera uma cópia visual da evidência com caixas YOLO, preservando o original."""

from __future__ import annotations

from io import BytesIO
from typing import Protocol

from PIL import Image, ImageDraw, ImageFont


class BoxDetection(Protocol):
    nome: str
    confianca: float
    bbox: tuple[int, int, int, int]


def annotate_evidence(content: bytes, detections: list[BoxDetection]) -> tuple[bytes, int, int]:
    image = Image.open(BytesIO(content)).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(12, round(image.width / 70)))
    stroke = max(2, round(image.width / 420))

    for detection in detections:
        x1, y1, x2, y2 = detection.bbox
        label = f"{detection.nome.replace('_', ' ')} {detection.confianca:.0%}"
        draw.rectangle((x1, y1, x2, y2), outline="#ff7500", width=stroke)
        left, top, right, bottom = draw.textbbox((x1, y1), label, font=font)
        label_height = bottom - top + 8
        label_width = right - left + 10
        label_top = max(0, y1 - label_height)
        draw.rectangle((x1, label_top, x1 + label_width, label_top + label_height), fill="#ff7500")
        draw.text((x1 + 5, label_top + 3), label, fill="#071016", font=font)

    output = BytesIO()
    image.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue(), image.width, image.height
