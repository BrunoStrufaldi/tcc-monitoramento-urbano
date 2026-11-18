"""Cria os cadastros básicos do sistema. Não cria eventos.

Pode rodar várias vezes e não apaga nada que já existe.
"""

from app.database import Base, SessionLocal, engine
from app.models.fonte_dados import FonteDados

FONTES = (
    ("MotSP YOLO", "yolo", "Observações visuais revalidadas pelo modelo no servidor", True),
)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for nome, tipo, descricao, ativo in FONTES:
            if not db.query(FonteDados).filter(FonteDados.nome == nome).first():
                db.add(FonteDados(nome=nome, tipo=tipo, descricao=descricao, ativo=ativo))

        db.commit()

    print("Cadastros de referência inicializados. Nenhum evento foi criado.")


if __name__ == "__main__":
    main()
