"""Rotas de consulta sobre os modelos do YOLO e as câmeras monitoradas.

Nenhuma delas grava eventos. Os eventos vêm só do monitoramento das câmeras.
"""

import sys
from pathlib import Path

from fastapi import APIRouter

from app.config import settings
from app.services.cet_camera_catalog import CAMERAS

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.detector import CLASSES_URBANAS, status_detector, status_incident_detector  # noqa: E402

router = APIRouter(prefix="/deteccao", tags=["deteccao-yolo"])


@router.get("/classes")
def listar_classes() -> dict:
    return {
        "aviso": "As classes urbanas são mapeamentos configuráveis. Os pesos COCO padrão não detectam alagamento, fumaça ou incêndio.",
        "classes": [
            {"id": key, "nome": value["nome"], "severidade": value["severidade"], "tipo": value["tipo"]}
            for key, value in CLASSES_URBANAS.items()
        ]
    }


@router.get("/cameras")
def listar_cameras() -> list[dict]:
    """Câmeras da CET que o MotSP monitora. O painel usa para dizer se um local tem cobertura."""
    return [{"id": cam.id, "nome": cam.nome, "latitude": cam.latitude, "longitude": cam.longitude} for cam in CAMERAS]


@router.get("/status")
def obter_status_detector() -> dict:
    """Estado dos dois modelos. O deploy usa para conferir se os pesos subiram."""
    resultado = status_detector()
    resultado["incidente"] = status_incident_detector()
    resultado["min_veiculos_transito"] = settings.gx_transito_min_veiculos
    return resultado
