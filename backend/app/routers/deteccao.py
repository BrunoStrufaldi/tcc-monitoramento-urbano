"""Router de detecção de eventos urbanos via visão computacional."""

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ml.detector import detectar_imagem, detectar_video, CLASSES_URBANAS

router = APIRouter(prefix="/deteccao", tags=["deteccao-yolo"])


class DeteccaoResponse(BaseModel):
    classe_id: int
    nome: str
    confianca: float = Field(ge=0, le=1)
    severidade: str
    tipo: str
    bbox: tuple[int, int, int, int]


class DeteccaoRequest(BaseModel):
    """Para simulação sem upload real de imagem."""
    num_deteccoes: int | None = Field(None, ge=1, le=10)


class VideoDeteccaoResponse(BaseModel):
    total_frames: int
    total_deteccoes: int
    resumo_classes: dict[str, int]


@router.get("/classes")
def listar_classes() -> dict:
    """Retorna classes de eventos urbanos que o modelo detecta."""
    return {
        "classes": [
            {"id": k, "nome": v["nome"], "severidade": v["severidade"], "tipo": v["tipo"]}
            for k, v in CLASSES_URBANAS.items()
        ]
    }


@router.post("/imagem", response_model=list[DeteccaoResponse])
async def detectar_em_imagem(file: UploadFile = File(...)):
    """Detecta eventos urbanos em uma imagem enviada.

    Nota: Esta é uma prova de conceito simulada.
    Em produção, processaria a imagem com YOLO real.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Apenas imagens são aceitas (image/*)")

    # Simula detecção (em produção: salva imagem, roda YOLO, retorna resultados)
    deteccoes = detectar_imagem(file.filename or "upload")
    return [
        DeteccaoResponse(
            classe_id=d.classe_id,
            nome=d.nome,
            confianca=d.confianca,
            severidade=d.severidade,
            tipo=d.tipo,
            bbox=d.bbox,
        )
        for d in deteccoes
    ]


@router.post("/simular", response_model=list[DeteccaoResponse])
def simular_deteccao(payload: DeteccaoRequest | None = None):
    """Simula detecção sem enviar imagem — útil para demonstração e testes."""
    num = payload.num_deteccoes if payload else None
    deteccoes = detectar_imagem("simulacao_tcc", num_deteccoes=num)
    return [
        DeteccaoResponse(
            classe_id=d.classe_id,
            nome=d.nome,
            confianca=d.confianca,
            severidade=d.severidade,
            tipo=d.tipo,
            bbox=d.bbox,
        )
        for d in deteccoes
    ]


@router.post("/video", response_model=VideoDeteccaoResponse)
def detectar_em_video(num_frames: int = 30):
    """Simula detecção em frames de vídeo (prova de conceito)."""
    resultado = detectar_video("video_simulado", frames_totais=num_frames)
    return VideoDeteccaoResponse(**resultado)
