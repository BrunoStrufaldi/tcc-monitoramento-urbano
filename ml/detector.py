"""Módulo de detecção de eventos urbanos via YOLO (simulado para TCC).

Em produção, usaria ultralytics.YOLO para inferência real.
Este MVP simula detecções realistas para demonstrar o pipeline.
"""

import random
from dataclasses import dataclass, field


# Classes de eventos urbanos detectáveis
CLASSES_URBANAS = {
    0: {"nome": "buraco", "severidade": "alta", "tipo": "infraestrutura"},
    1: {"nome": "alagamento", "severidade": "critica", "tipo": "clima"},
    2: {"nome": "transito", "severidade": "media", "tipo": "mobilidade"},
    3: {"nome": "lixo", "severidade": "baixa", "tipo": "meio_ambiente"},
    4: {"nome": "incendio", "severidade": "critica", "tipo": "seguranca"},
    5: {"nome": "construcao_irregular", "severidade": "alta", "tipo": "urbanismo"},
    6: {"nome": "arvore_caida", "severidade": "media", "tipo": "infraestrutura"},
    7: {"nome": "vazamento", "severidade": "alta", "tipo": "infraestrutura"},
}


@dataclass
class Deteccao:
    """Resultado de uma detecção YOLO."""
    classe_id: int
    nome: str
    confianca: float
    severidade: str
    tipo: str
    bbox: tuple[int, int, int, int] = field(default_factory=lambda: (0, 0, 100, 100))


def detectar_imagem(caminho_imagem: str = "simulacao", num_deteccoes: int | None = None) -> list[Deteccao]:
    """Simula detecção YOLO em uma imagem.

    Args:
        caminho_imagem: Caminho da imagem (usado apenas para logging).
        num_deteccoes: Número de detecções a retornar (None = aleatório 1-3).

    Returns:
        Lista de detecções encontradas.
    """
    if num_deteccoes is None:
        num_deteccoes = random.randint(1, 3)

    resultados: list[Deteccao] = []
    classes_disponiveis = list(CLASSES_URBANAS.keys())

    for _ in range(min(num_deteccoes, len(classes_disponiveis))):
        classe_id = random.choice(classes_disponiveis)
        classes_disponiveis.remove(classe_id)
        meta = CLASSES_URBANAS[classe_id]

        confianca = round(random.uniform(0.55, 0.98), 3)
        x1 = random.randint(0, 400)
        y1 = random.randint(0, 300)
        w = random.randint(50, 200)
        h = random.randint(50, 200)

        resultados.append(Deteccao(
            classe_id=classe_id,
            nome=meta["nome"],
            confianca=confianca,
            severidade=meta["severidade"],
            tipo=meta["tipo"],
            bbox=(x1, y1, x1 + w, y1 + h),
        ))

    return sorted(resultados, key=lambda d: d.confianca, reverse=True)


def detectar_video(frame_path: str = "simulacao_frame", frames_totais: int = 30) -> dict:
    """Simula detecção em frames de vídeo.

    Returns:
        Dict com total_frames, deteccoes_por_frame, resumo.
    """
    deteccoes_por_frame: list[list[dict]] = []
    total_deteccoes = 0

    for i in range(frames_totais):
        deteccoes = detectar_imagem(f"frame_{i}", num_deteccoes=random.randint(0, 2))
        frame_data = [
            {
                "classe_id": d.classe_id,
                "nome": d.nome,
                "confianca": d.confianca,
                "severidade": d.severidade,
            }
            for d in deteccoes
        ]
        deteccoes_por_frame.append(frame_data)
        total_deteccoes += len(deteccoes)

    contagem_classes: dict[str, int] = {}
    for frame in deteccoes_por_frame:
        for d in frame:
            contagem_classes[d["nome"]] = contagem_classes.get(d["nome"], 0) + 1

    return {
        "total_frames": frames_totais,
        "total_deteccoes": total_deteccoes,
        "deteccoes_por_frame": deteccoes_por_frame,
        "resumo_classes": contagem_classes,
    }
