"""Inicializa apenas cadastros de referência; nunca cria eventos operacionais.

Eventos devem entrar pela API, por uma integração real ou pelo fluxo YOLO com
evidência. Este script é idempotente e não apaga dados existentes.
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
    ("Painel manual", "manual", "Ocorrências registradas por operador", True),
    ("MotSP YOLO", "yolo", "Observações visuais revalidadas pelo modelo no servidor", True),
    ("Open-Meteo", "api", "Clima e qualidade do ar consultados em tempo real", True),
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
