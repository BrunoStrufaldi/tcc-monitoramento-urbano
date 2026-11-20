"""Regras para detectar alagamento na imagem de uma câmera da CET-SP.

Usa o modelo de alagamento. Quando ele encontra água na pista, o sistema também
busca a chuva no local, o aviso do INMET e o histórico de alagamento da via, e
esses dados ajudam a decidir se o alerta é confiável. Quem chama estas regras é
o ciclo de monitoramento (ciclo_monitoramento.py).
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.config import settings
from app.services.detection_events import Analise
from app.services.inmet_alert_source import obter_aviso_ativo
from app.services.weather_source import obter_condicoes_atuais
from data_fusion.historico_alagamento import indice_historico
from ml.detector import detectar_incidentes_imagem

logger = logging.getLogger(__name__)

TIPO = "alagamento"


def analisar_frame(conteudo: bytes, latitude: float, longitude: float, nome_camera: str) -> Analise | None:
    """Diz se a imagem mostra alagamento.

    Devolve a análise quando há alagamento e None quando não há. Se o modelo
    não estiver disponível, a exceção sobe para o ciclo tratar.
    """
    caminho = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as arquivo:
            arquivo.write(conteudo)
            caminho = arquivo.name
        deteccoes = detectar_incidentes_imagem(caminho, settings.gx_yolo_incident_conf)
    finally:
        if caminho:
            Path(caminho).unlink(missing_ok=True)

    alagamento = next((item for item in deteccoes if item.nome == "alagamento"), None)
    if alagamento is None:
        return None

    contexto: list[tuple[str, float, str]] = []
    condicoes = obter_condicoes_atuais(latitude, longitude)
    if condicoes.get("disponivel") and condicoes.get("chuva_mm") is not None:
        contexto.append(("precipitacao_mm_h", float(condicoes["chuva_mm"]), "mm/h"))

    aviso = obter_aviso_ativo()
    if aviso.get("disponivel") and aviso.get("menciona_alagamento"):
        contexto.append(("alerta_inmet_severidade", float(aviso["severidade_indice"]), "indice_0_10"))

    # O histórico é gravado mesmo quando é zero, para separar uma via que nunca
    # alagou de uma via sem informação.
    indice_hist, descricao_hist = indice_historico(latitude, longitude)
    contexto.append(("historico_alagamento_indice", indice_hist, "indice_0_10"))

    logger.info(
        "Alagamento visto em %s (confiança %.0f%%), histórico da via: %s",
        nome_camera, alagamento.confianca * 100, descricao_hist,
    )
    return Analise(
        deteccao=alagamento,
        fonte_nome=f"MotSP YOLO Contínuo (alagamento) - {nome_camera}",
        fonte_descricao=f"Modelo dedicado de incidentes rodando direto na câmera pública CET-SP '{nome_camera}', sem confirmação humana.",
        modelo_ia="YOLO11 (modelo de incidentes GX)",
        origem="camera_continua_alagamento",
        contexto=contexto,
    )
