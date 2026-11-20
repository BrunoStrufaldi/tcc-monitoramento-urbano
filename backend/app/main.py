import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope
from starlette.responses import Response

from app.broadcast import set_main_loop
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    dados_contextuais,
    deteccao,
    evidencias,
    eventos,
    fontes,
    fusion,
    localizacoes,
    logs,
    monitoramento,
    tempo_real,
    websocket,
)
from app.services import ciclo_monitoramento
from app.services.data_fusion_service import migrar_categoria_legada, promover_eventos_por_confiabilidade
from app.services.detection_events import preencher_enderecos_das_cameras
from app.services.event_retention import colapsar_eventos_duplicados


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Localmente o projeto usa SQLite. O schema do MySQL fica em database/schema.sql.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        migrar_categoria_legada(db)
        colapsar_eventos_duplicados(db)
        promover_eventos_por_confiabilidade(db)
        preencher_enderecos_das_cameras(db)
    set_main_loop(asyncio.get_running_loop())
    # Vem desligado por padrão, inclusive nos testes. Para ligar, use
    # GX_MONITORAMENTO_ATIVO=true no .env. Na nuvem a CPU só existe com o painel
    # aberto, então o monitoramento anda só enquanto alguém está usando.
    if settings.gx_monitoramento_ativo:
        ciclo_monitoramento.iniciar()
    yield
    ciclo_monitoramento.parar()


app = FastAPI(
    title="MotSP",
    description="Monitoramento Urbano de São Paulo: alagamento e trânsito detectados em câmeras públicas, em tempo real.",
    version="0.1.0",
    lifespan=lifespan,
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
app.include_router(logs.router)
app.include_router(fontes.router)
app.include_router(localizacoes.router)
app.include_router(evidencias.router)
app.include_router(dados_contextuais.router)
app.include_router(tempo_real.router)
app.include_router(deteccao.router)
app.include_router(monitoramento.router)
app.include_router(websocket.router)


def _status() -> dict[str, str]:
    return {"status": "online", "message": "API do TCC rodando com sucesso"}


# Endereço para checar se a API está no ar, já que "/" mostra o painel.
app.add_api_route("/api/status", _status, methods=["GET"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Painel servido pela própria API. Precisa ser a última rota registrada,
# senão ele responderia no lugar das outras.
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


class _PainelStaticFiles(StaticFiles):
    """Arquivos do painel com cache desligado no HTML e no JavaScript.

    Sem isso o Safari do iPhone continuava mostrando a versão antiga do painel
    mesmo depois de um deploy.
    """

    _SEM_CACHE = ("text/html", "text/javascript", "application/javascript")

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.headers.get("content-type", "").startswith(self._SEM_CACHE):
            response.headers["Cache-Control"] = "no-cache"
        return response


if settings.gx_serve_frontend and _FRONTEND_DIR.is_dir():
    app.mount("/", _PainelStaticFiles(directory=_FRONTEND_DIR, html=True), name="painel")
else:
    app.add_api_route("/", _status, methods=["GET"])
