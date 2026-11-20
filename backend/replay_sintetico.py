"""Replay sintético do MotSP, com saída esperada.

Roda o ciclo de monitoramento com entradas fixas e mostra o que acontece com
os eventos: as regras de trânsito e de alagamento, a fusão, os dois ritmos do
monitoramento (câmera sem evento a cada 60 s, câmera com evento no ciclo geral
de 10 min), a atualização do mesmo evento, a remoção depois de dois ciclos sem
confirmação e a câmera travada. Não usa imagens reais, internet,
GPU nem os modelos YOLO. A contagem do YOLO e as respostas da TomTom, do clima e
do INMET são simuladas, e o banco é um SQLite em memória.

O resultado é comparado com replay_saida_esperada.txt. Se tudo bater, o script
termina com código 0.

Uso (a partir de backend/):
    venv\\Scripts\\python replay_sintetico.py
    venv\\Scripts\\python replay_sintetico.py --gravar   # regrava a saída esperada
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
import tempfile
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path
from unittest import mock

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent
for _caminho in (str(BACKEND_DIR), str(PROJECT_ROOT)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import httpx  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401
from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.dado_contextual import DadoContextual  # noqa: E402
from app.models.evento import Evento  # noqa: E402
from app.services import ciclo_monitoramento, detection_events, event_retention, flood_detection, live_detection  # noqa: E402
from app.services.ciclo_monitoramento import CameraMonitorada  # noqa: E402
from ml.detector import Deteccao  # noqa: E402

SAIDA_ESPERADA = BACKEND_DIR / "replay_saida_esperada.txt"

# Limiares da versão avaliada. São os padrões do config.py, os mesmos do Cloud Run.
# O replay fixa esses valores para não depender do .env da máquina.
LIMIARES = {
    "yolo_threshold": 0.45,
    "gx_yolo_incident_conf": 0.6,
    "gx_transito_min_veiculos_corroborado": 4,
    "gx_transito_min_veiculos": 12,
    "gx_transito_min_veiculos_confirmado": 16,
    "gx_transito_tomtom_indice_minimo": 3.0,
    "gx_ciclo_minutos": 10.0,
    "gx_ciclo_sem_evento_segundos": 60.0,
    "gx_ciclos_sem_confirmacao_para_remover": 2,
    "gx_camera_frescor_maximo_segundos": 300.0,
    "gx_fusion_auto_ativo_min": 0.80,
}

_SEM_TOMTOM = {"disponivel": False}
_DATA_HTTP = re.compile(r"\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT")
# Esta mensagem traz a duração e a hora do ciclo, que mudam a cada execução. O
# replay escreve o resumo do ciclo por conta própria.
_LOG_IGNORADO = "Passada "


def _veiculos(quantidade: int) -> list[Deteccao]:
    return [
        Deteccao(8, "veiculo", 0.8, "baixa", "observacao_visual", (i * 10, 0, i * 10 + 8, 8), "car")
        for i in range(quantidade)
    ]


def _alagamento(confianca: float) -> list[Deteccao]:
    return [Deteccao(1, "alagamento", confianca, "critica", "alagamento", (0, 0, 50, 50), "flood")]


def _camera(lat: float, transito: bool = True, alagamento: bool = False) -> CameraMonitorada:
    return CameraMonitorada(f"http://camera-sintetica/{lat}.jpg", lat, -46.63, f"câmera sintética {lat}", transito, alagamento)


class _Coletor(logging.Handler):
    """Guarda as mensagens de log do sistema para entrarem na saída do replay."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.linhas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        mensagem = record.getMessage()
        if mensagem.startswith(_LOG_IGNORADO):
            return
        # A data do frame muda a cada execução, então vira um marcador fixo.
        mensagem = _DATA_HTTP.sub("<data do frame>", mensagem)
        self.linhas.append(f"    log {record.levelname}: {mensagem}")


class _Replay:
    def __init__(self, pilha: ExitStack) -> None:
        self.pilha = pilha
        self.saida: list[str] = []
        self.coletor = _Coletor()
        self.contador_frames = 0
        # Próximo frame que a câmera falsa vai mandar, como (conteúdo, idade em
        # segundos). Sem nada aqui, ela manda um frame novo e atual.
        self.proximo_frame: tuple[bytes, int] | None = None

        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        Base.metadata.create_all(bind=engine)
        self.sessao = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
        pilha.callback(self.sessao.close)

        @contextmanager
        def _sessao():
            yield self.sessao

        replay = self

        class _Resposta:
            def __init__(self, conteudo: bytes, idade: int) -> None:
                self.content = conteudo
                data = datetime.now(UTC) - timedelta(seconds=idade)
                self.headers = httpx.Headers({"last-modified": format_datetime(data, usegmt=True)})

            def raise_for_status(self) -> None:
                return None

        class _Cliente:
            def __init__(self, *_a, **_k) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a) -> bool:
                return False

            def get(self, _url):
                if replay.proximo_frame is not None:
                    return _Resposta(*replay.proximo_frame)
                replay.contador_frames += 1
                return _Resposta(f"frame-sintetico-{replay.contador_frames}".encode(), 30)

        evidencias = Path(pilha.enter_context(tempfile.TemporaryDirectory(prefix="motsp-replay-")))
        trocas = [
            (ciclo_monitoramento, "SessionLocal", lambda: _sessao()),
            (ciclo_monitoramento.httpx, "Client", _Cliente),
            (ciclo_monitoramento, "_ciclos_sem_confirmacao", {}),
            (ciclo_monitoramento, "_ultimo_hash", {}),
            (detection_events, "_EVIDENCIAS_DIR", evidencias),
            (detection_events, "annotate_evidence", lambda conteudo, _d: (conteudo, 640, 360)),
            (flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": False}),
            (flood_detection, "obter_aviso_ativo", lambda: {"disponivel": False}),
            (flood_detection, "indice_historico", lambda _lat, _lon: (0.0, "sem histórico")),
            (event_retention, "_publicar_remocoes", lambda _ids: None),
        ]
        for modulo, nome, valor in trocas:
            pilha.enter_context(mock.patch.object(modulo, nome, valor))
        for nome, valor in LIMIARES.items():
            pilha.enter_context(mock.patch.object(settings, nome, valor))

        for nome in ("app.services.live_detection", "app.services.flood_detection", "app.services.ciclo_monitoramento"):
            logger = logging.getLogger(nome)
            pilha.callback(logger.setLevel, logger.level)
            logger.setLevel(logging.INFO)
            logger.addHandler(self.coletor)
            pilha.callback(logger.removeHandler, self.coletor)

    def escrever(self, texto: str) -> None:
        self.saida.extend(self.coletor.linhas)
        self.coletor.linhas.clear()
        self.saida.append(texto)

    def _descrever(self, evento: Evento) -> str:
        contexto = {
            d.chave: float(d.valor_numerico)
            for d in self.sessao.query(DadoContextual).filter(DadoContextual.evento_id == evento.id).order_by(DadoContextual.chave)
        }
        partes = ", ".join(f"{chave}={valor:g}" for chave, valor in contexto.items()) or "nenhum"
        return (
            f"    evento #{evento.id} tipo={evento.tipo} status={evento.status} "
            f"confiabilidade={float(evento.confianca):.2f} contexto: {partes}"
        )

    def ciclo(
        self,
        rotulo: str,
        camera: CameraMonitorada,
        *,
        veiculos: int = 0,
        tomtom: dict | None = None,
        alagamento: float | None = None,
        chuva: float | None = None,
        inmet: float | None = None,
        historico: float = 0.0,
        modo: str = "completo",
    ) -> None:
        """Roda uma passada com uma câmera só e mostra o que ficou no ponto dela."""
        consultas: list[int] = []
        chamadas_yolo: list[int] = []

        def _tomtom(_lat, _lon):
            consultas.append(1)
            return _SEM_TOMTOM if tomtom is None else tomtom

        def _yolo(_caminho, _limiar):
            chamadas_yolo.append(1)
            return _veiculos(veiculos)

        clima = {"disponivel": True, "chuva_mm": chuva} if chuva is not None else {"disponivel": False}
        aviso = (
            {"disponivel": True, "menciona_alagamento": True, "severidade_indice": inmet}
            if inmet is not None else {"disponivel": False}
        )
        incidentes = _alagamento(alagamento) if alagamento is not None else []

        self.escrever(rotulo)
        with mock.patch.object(ciclo_monitoramento, "cameras_monitoradas", lambda: [camera]), \
             mock.patch.object(live_detection, "detectar_imagem_real", _yolo), \
             mock.patch.object(live_detection, "obter_fluxo_transito", _tomtom), \
             mock.patch.object(flood_detection, "detectar_incidentes_imagem", lambda _c, _t: chamadas_yolo.append(1) or incidentes), \
             mock.patch.object(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: clima), \
             mock.patch.object(flood_detection, "obter_aviso_ativo", lambda: aviso), \
             mock.patch.object(flood_detection, "indice_historico", lambda _lat, _lon: (historico, f"índice {historico:g}")):
            resumo = ciclo_monitoramento.executar_ciclo(modo)

        self.saida.extend(self.coletor.linhas)
        self.coletor.linhas.clear()
        self.saida.append(
            f"    YOLO chamado: {len(chamadas_yolo)}x, TomTom consultada: {'sim' if consultas else 'não'}"
        )
        self.saida.append(
            f"    passada {modo}: " + ", ".join(
                f"{chave}={resumo[chave]}"
                for chave in ("cameras", "sem_imagem", "criados", "atualizados", "sem_confirmacao", "removidos", "falhas")
            )
        )
        self.sessao.expire_all()
        tipos = ([live_detection.TIPO] if camera.transito else []) + ([flood_detection.TIPO] if camera.alagamento else [])
        eventos = [
            evento for tipo in tipos
            if (evento := detection_events.buscar_evento_no_ponto(
                self.sessao, tipo=tipo, latitude=camera.latitude, longitude=camera.longitude,
            )) is not None
        ]
        if not eventos:
            self.saida.append("    no mapa: nenhum evento nesta câmera")
        for evento in eventos:
            self.saida.append(self._descrever(evento))


def executar() -> list[str]:
    with ExitStack() as pilha:
        r = _Replay(pilha)
        r.saida.append("MotSP replay sintético")
        r.saida.append(
            "limiares: " + ", ".join(f"{k}={v}" for k, v in LIMIARES.items())
        )

        r.saida.append("")
        r.saida.append("== Trânsito (um ciclo numa câmera sem evento) ==")
        r.ciclo("[T1] 18 veículos, TomTom fora do ar", _camera(-23.50), veiculos=18)
        r.ciclo("[T2] 13 veículos, TomTom diz trecho fluindo (índice 1,0)", _camera(-23.51),
                veiculos=13, tomtom={"disponivel": True, "indice_congestionamento": 1.0})
        r.ciclo("[T3] 6 veículos, TomTom confirma lentidão (índice 8,0)", _camera(-23.52),
                veiculos=6, tomtom={"disponivel": True, "indice_congestionamento": 8.0})
        r.ciclo("[T4] 6 veículos, TomTom fora do ar", _camera(-23.53), veiculos=6)
        r.ciclo("[T5] 3 veículos, abaixo do piso", _camera(-23.54),
                veiculos=3, tomtom={"disponivel": True, "indice_congestionamento": 9.0})

        r.saida.append("")
        r.saida.append("== Alagamento (um ciclo numa câmera sem evento) ==")
        so_alagamento = {"transito": False, "alagamento": True}
        r.ciclo("[A1] YOLO vê alagamento (0,81) sem chuva, aviso nem histórico",
                _camera(-23.60, **so_alagamento), alagamento=0.81)
        r.ciclo("[A2] YOLO vê alagamento (0,81) com chuva de 30 mm/h, aviso INMET 9,5 e via que alaga sempre",
                _camera(-23.61, **so_alagamento), alagamento=0.81, chuva=30.0, inmet=9.5, historico=9.0)

        r.saida.append("")
        r.saida.append("== Os dois ritmos na mesma câmera ==")
        camera = _camera(-23.70)
        r.ciclo("[K1] verificação de 60 s: 6 veículos e TomTom confirma (índice 8,0)", camera,
                veiculos=6, tomtom={"disponivel": True, "indice_congestionamento": 8.0}, modo="sem_evento")
        r.ciclo("[K2] verificação de 60 s seguinte: a câmera já tem evento e fica de fora", camera,
                veiculos=18, modo="sem_evento")
        r.ciclo("[K3] ciclo geral: 18 veículos, o mesmo evento é atualizado", camera,
                veiculos=18, modo="com_evento")
        r.ciclo("[K4] ciclo geral: 2 veículos, primeiro ciclo sem confirmação", camera,
                veiculos=2, modo="com_evento")
        r.ciclo("[K5] ciclo geral: 2 veículos, segundo ciclo sem confirmação", camera,
                veiculos=2, modo="com_evento")
        r.ciclo("[K6] verificação de 60 s: sem evento, a câmera volta a ser olhada", camera,
                veiculos=2, modo="sem_evento")

        r.saida.append("")
        r.saida.append("== Câmera sem imagem nova ==")
        camera = _camera(-23.80)
        r.ciclo("[C1] verificação de 60 s: 18 veículos", camera, veiculos=18, modo="sem_evento")
        r.proximo_frame = (b"frame-velho", 600)
        r.ciclo("[C2] ciclo geral: câmera travada, frame com 10 min de idade", camera,
                veiculos=2, modo="com_evento")
        r.proximo_frame = (b"frame-repetido", 30)
        r.ciclo("[C3] ciclo geral: frame novo, mas sem trânsito", camera, veiculos=2, modo="com_evento")
        r.ciclo("[C4] ciclo geral: a câmera manda o mesmo frame do anterior", camera,
                veiculos=2, modo="com_evento")
        r.proximo_frame = None
        return r.saida


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--gravar", action="store_true", help="regrava a saída esperada com o resultado atual")
    args = parser.parse_args()

    saida = executar()
    texto = "\n".join(saida) + "\n"
    print(texto, end="")

    if args.gravar:
        SAIDA_ESPERADA.write_text(texto, encoding="utf-8")
        print(f"\nSaída esperada gravada em {SAIDA_ESPERADA.name}")
        return 0

    esperado = SAIDA_ESPERADA.read_text(encoding="utf-8")
    if texto == esperado:
        print("\nOK: a saída é igual à esperada.")
        return 0
    print("\nDIFERENTE da saída esperada:")
    import difflib
    print("".join(difflib.unified_diff(esperado.splitlines(True), texto.splitlines(True), "esperada", "obtida")))
    return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
