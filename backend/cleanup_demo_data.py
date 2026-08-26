"""Remove somente o conjunto demonstrativo legado do SQLite local.

Cria uma cópia integral antes da alteração. O filtro usa os títulos exatos do
seed antigo e nunca remove eventos cuja fonte seja YOLO.
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


DATABASE = Path(__file__).resolve().parent / "gx.db"
BACKUP_DIR = Path(__file__).resolve().parent / "data" / "backups"
DEMO_TITLES = (
    "Congestionamento na Av. Principal",
    "Alagamento reportado na Zona Norte",
    "Fumaça em área comercial",
    "Árvore caída bloqueia via em Santana",
    "Buraco na pista da Vila Mariana",
)


def main(apply: bool) -> None:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in DEMO_TITLES)
    query = f"""
        SELECT e.id, e.titulo, e.localizacao_id
        FROM eventos e
        LEFT JOIN fontes_dados f ON f.id = e.fonte_id
        WHERE e.titulo IN ({placeholders})
          AND COALESCE(f.tipo, '') <> 'yolo'
        ORDER BY e.id
    """
    rows = connection.execute(query, DEMO_TITLES).fetchall()
    print(f"Registros demonstrativos identificados: {len(rows)}")
    for row in rows:
        print(f"  #{row['id']} {row['titulo']}")

    if not apply or not rows:
        connection.close()
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"gx-before-demo-cleanup-{datetime.now():%Y%m%d-%H%M%S}.db"
    backup = sqlite3.connect(backup_path)
    connection.backup(backup)
    backup.close()

    event_ids = [row["id"] for row in rows]
    location_ids = [row["localizacao_id"] for row in rows]
    event_marks = ",".join("?" for _ in event_ids)
    location_marks = ",".join("?" for _ in location_ids)
    with connection:
        for table in ("notificacoes", "dados_contextuais", "evidencias_visuais"):
            connection.execute(f"DELETE FROM {table} WHERE evento_id IN ({event_marks})", event_ids)
        connection.execute(f"UPDATE logs_sistema SET evento_id = NULL WHERE evento_id IN ({event_marks})", event_ids)
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='auditoria_acoes'").fetchone():
            connection.execute(f"UPDATE auditoria_acoes SET evento_id = NULL WHERE evento_id IN ({event_marks})", event_ids)
        connection.execute(f"DELETE FROM eventos WHERE id IN ({event_marks})", event_ids)
        connection.execute(
            f"DELETE FROM localizacoes WHERE id IN ({location_marks}) AND NOT EXISTS "
            "(SELECT 1 FROM eventos WHERE eventos.localizacao_id = localizacoes.id)",
            location_ids,
        )

    connection.close()
    print(f"Limpeza concluída. Backup recuperável: {backup_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Aplica a limpeza após criar backup")
    main(parser.parse_args().apply)
