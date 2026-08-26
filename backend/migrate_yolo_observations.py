"""Revalida evidências YOLO legadas e corrige conclusões sem suporte visual."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
if str(PROJECT_ROOT) in sys.path:
    sys.path.remove(str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from ml.detector import detectar_imagem_real  # noqa: E402
from backend.app.services.evidence_annotation import annotate_evidence  # noqa: E402


DATABASE = BACKEND_DIR / "gx.db"
EVIDENCE_DIR = BACKEND_DIR / "data" / "evidencias"
DISPLAY_NAMES = {"veiculo": "veículo", "onibus": "ônibus", "caminhao": "caminhão"}


def main() -> None:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT e.id AS evento_id, ev.id AS evidencia_id, ev.caminho_arquivo,
               ev.metadados, l.id AS localizacao_id
        FROM eventos e
        JOIN fontes_dados f ON f.id = e.fonte_id AND f.tipo = 'yolo'
        JOIN evidencias_visuais ev ON ev.evento_id = e.id
        JOIN localizacoes l ON l.id = e.localizacao_id
        WHERE ev.caminho_arquivo IS NOT NULL
        ORDER BY ev.id
        """
    ).fetchall()

    changed = 0
    for row in rows:
        path = EVIDENCE_DIR / row["caminho_arquivo"]
        if not path.is_file():
            print(f"Evidência ausente; evento #{row['evento_id']} preservado sem alteração: {path}")
            continue
        detections = detectar_imagem_real(str(path), 0.45)
        if not detections:
            print(f"Nenhuma detecção revalidada; evento #{row['evento_id']} preservado sem alteração")
            continue

        detection = detections[0]
        original_bytes = path.read_bytes()
        annotated_name = path.stem + "-yolo.jpg"
        annotated, width, height = annotate_evidence(original_bytes, detections)
        (EVIDENCE_DIR / annotated_name).write_bytes(annotated)
        label = DISPLAY_NAMES.get(detection.nome, detection.nome.replace("_", " "))
        object_observation = detection.tipo == "observacao_visual"
        title = (
            f"Observação YOLO: {label} detectado"
            if object_observation
            else f"Possível {label} detectado pelo YOLO"
        )
        description = (
            "Detecção visual produzida pelo YOLO11 em frame real da câmera pública CET-SP 225. "
            "A imagem comprova a presença do objeto, não congestionamento ou outro incidente."
            if object_observation
            else "Sinal visual produzido pelo YOLO11 em imagem real; ocorrência em análise operacional."
        )
        try:
            metadata = json.loads(row["metadados"] or "{}")
        except json.JSONDecodeError:
            metadata = {}
        metadata.update(
            {
                "origem": "camera_publica_cet_sp",
                "camera_id": 225,
                "camera_local": "Av. Ascendino Reis x Rua Pedro de Toledo",
                "camera_url": "https://cameras.cetsp.com.br/Cams/225/1.jpg",
                "classe_modelo": detection.classe_modelo,
                "bbox": detection.bbox,
                "validado_no_servidor": True,
                "observacao_nao_e_incidente": object_observation,
                "sha256_original": hashlib.sha256(original_bytes).hexdigest(),
                "arquivo_original": row["caminho_arquivo"],
                "revalidado_em": datetime.now(UTC).isoformat(),
            }
        )
        with connection:
            connection.execute(
                """
                UPDATE eventos
                SET titulo = ?, descricao = ?, tipo = ?, severidade = ?,
                    status = 'em_analise', confianca = ?, atualizado_em = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (title, description, detection.tipo, detection.severidade, detection.confianca, row["evento_id"]),
            )
            connection.execute(
                """
                UPDATE evidencias_visuais
                SET modelo_ia = 'YOLO11n/COCO (revalidado no servidor)',
                    classe_detectada = ?, confianca = ?, metadados = ?,
                    caminho_arquivo = ?, largura_px = ?, altura_px = ?
                WHERE id = ?
                """,
                (
                    detection.nome,
                    detection.confianca,
                    json.dumps(metadata, ensure_ascii=False),
                    annotated_name,
                    width,
                    height,
                    row["evidencia_id"],
                ),
            )
            connection.execute(
                """
                UPDATE localizacoes
                SET endereco = 'Av. Ascendino Reis x Rua Pedro de Toledo',
                    bairro = 'Vila Clementino', cidade = 'São Paulo'
                WHERE id = ?
                """,
                (row["localizacao_id"],),
            )
        changed += 1
        print(f"Evento #{row['evento_id']} revalidado: {title} ({detection.confianca:.1%})")

    connection.close()
    print(f"Observações atualizadas: {changed}")


if __name__ == "__main__":
    main()
