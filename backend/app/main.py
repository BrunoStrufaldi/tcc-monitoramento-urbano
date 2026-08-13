from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    dados_contextuais,
    deteccao,
    evidencias,
    eventos,
    fontes,
    fusion,
    localizacoes,
    logs,
    notificacoes,
    regioes,
    tempo_real,
)

app = FastAPI(
    title="Notificações Urbanas",
    description="Sistema de notificações urbanas em tempo real para TCC",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(eventos.router)
app.include_router(fusion.router)
app.include_router(notificacoes.router)
app.include_router(logs.router)
app.include_router(regioes.router)
app.include_router(fontes.router)
app.include_router(localizacoes.router)
app.include_router(evidencias.router)
app.include_router(dados_contextuais.router)
app.include_router(tempo_real.router)
app.include_router(deteccao.router)


@app.get("/")
def raiz() -> dict[str, str]:
    return {"status": "online", "message": "API do TCC rodando com sucesso"}


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
