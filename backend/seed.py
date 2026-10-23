"""Cria os cadastros básicos do sistema. Não cria eventos.

Pode rodar várias vezes e não apaga nada que já existe.
"""

from app.database import Base, SessionLocal, engine
from app.models.fonte_dados import FonteDados
from app.models.regiao import Regiao


REGIOES = (
    ("Centro", "CENTRO", "Região central da cidade"),
    ("Zona Norte", "ZN", "Bairros da zona norte"),
    ("Zona Sul", "ZS", "Bairros da zona sul"),
)

FONTES = (
    ("MotSP YOLO", "yolo", "Observações visuais revalidadas pelo modelo no servidor", True),
)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for nome, codigo, descricao in REGIOES:
            if not db.query(Regiao).filter(Regiao.codigo == codigo).first():
                db.add(Regiao(nome=nome, codigo=codigo, descricao=descricao))

        for nome, tipo, descricao, ativo in FONTES:
            if not db.query(FonteDados).filter(FonteDados.nome == nome).first():
                db.add(FonteDados(nome=nome, tipo=tipo, descricao=descricao, ativo=ativo))

        db.commit()

    print("Cadastros de referência inicializados. Nenhum evento foi criado.")


if __name__ == "__main__":
    main()
