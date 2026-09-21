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
    regioes,
    tempo_real,
    websocket,
)
from app.services import flood_detection, live_detection
from app.services.data_fusion_service import promover_eventos_por_confiabilidade
from app.services.event_retention import colapsar_eventos_duplicados, purgar_eventos_expirados


async def _manutencao_periodica() -> None:
    """Mantém o quadro em tempo real: remove eventos fora da janela, colapsa
    pilhas do mesmo tipo no mesmo ponto e promove para "ativo" os eventos que
    já batem o limiar de confiabilidade."""
    while True:
        try:
            with SessionLocal() as db:
                purgar_eventos_expirados(db)
                colapsar_eventos_duplicados(db)
                promover_eventos_por_confiabilidade(db)
        except Exception:
            pass
        await asyncio.sleep(120)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # O SQLite local permite executar o projeto sem depender de um MySQL externo.
    # Em produção, o schema MySQL continua sendo aplicado via database/schema.sql.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        purgar_eventos_expirados(db)
        colapsar_eventos_duplicados(db)
        promover_eventos_por_confiabilidade(db)
    set_main_loop(asyncio.get_running_loop())
    manutencao_task = asyncio.create_task(_manutencao_periodica())
    # Desligado por padrão (inclusive em testes) — evita threads de rede reais
    # subindo sozinhas. Ative com GX_MONITORAMENTO_ATIVO=true no .env.
    if settings.gx_monitoramento_ativo:
        live_detection.iniciar()
        flood_detection.iniciar()
    yield
    manutencao_task.cancel()
    live_detection.parar()
    flood_detection.parar()


app = FastAPI(
    title="Notificações Urbanas",
    description="Sistema de notificações urbanas em tempo real para TCC",
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
app.include_router(regioes.router)
app.include_router(fontes.router)
app.include_router(localizacoes.router)
app.include_router(evidencias.router)
app.include_router(dados_contextuais.router)
app.include_router(tempo_real.router)
app.include_router(deteccao.router)
app.include_router(websocket.router)


def _status() -> dict[str, str]:
    return {"status": "online", "message": "API do TCC rodando com sucesso"}


# Sempre disponível: no deploy o "/" é o painel, e sobrou este endereço para
# checar a API sem depender do HTML.
app.add_api_route("/api/status", _status, methods=["GET"])


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# Painel estático servido pela própria API (deploy em container).
#
# O mount tem que ser a ÚLTIMA rota registrada: ele responde por "/" inteiro e
# engoliria /eventos, /ws e /docs se viesse antes dos routers. Pela mesma razão
# o "/" JSON só existe quando o painel NÃO está sendo servido — com o mount
# ativo, quem abre o link recebe o index.html, não um dicionário.
_FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"


class _PainelStaticFiles(StaticFiles):
    """StaticFiles com ``Cache-Control: no-cache`` no HTML.

    O index.html é quem aponta para o CSS/JS versionados pelo ``?v=``. Sem
    cabeçalho de cache o Safari do iOS reaproveitava o HTML antigo por horas
    (cache heurístico) e continuava carregando o CSS antigo mesmo depois de um
    deploy. ``no-cache`` obriga a revalidar pelo ETag a cada abertura — um 304
    barato — e os demais arquivos ficam com o cache padrão.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.headers.get("content-type", "").startswith("text/html"):
            response.headers["Cache-Control"] = "no-cache"
        return response


if settings.gx_serve_frontend and _FRONTEND_DIR.is_dir():
    app.mount("/", _PainelStaticFiles(directory=_FRONTEND_DIR, html=True), name="painel")
else:
    app.add_api_route("/", _status, methods=["GET"])
