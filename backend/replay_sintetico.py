"""Replay sintético do MotSP, com saída esperada.

Roda as regras de trânsito, alagamento, frescor da câmera, imagem repetida,
fusão e expiração com entradas fixas. Não usa imagens reais, internet, GPU nem
os modelos YOLO. A contagem do YOLO e as respostas da TomTom, do clima e do
INMET são simuladas, e o banco é um SQLite em memória.

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
from app.models.localizacao import Localizacao  # noqa: E402
from app.services import detection_events, event_retention, flood_detection, live_detection  # noqa: E402
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
    "gx_alerta_cooldown_seconds": 1800.0,
    "gx_transito_veto_cooldown_seconds": 600.0,
    "gx_camera_frescor_maximo_segundos": 300.0,
    "gx_evento_janela_minutos": 45,
    "gx_fusion_auto_ativo_min": 0.80,
}

_SEM_TOMTOM = {"disponivel": False}
_DATA_HTTP = re.compile(r"\w{3}, \d{2} \w{3} \d{4} \d{2}:\d{2}:\d{2} GMT")


def _veiculos(quantidade: int) -> list[Deteccao]:
    return [
        Deteccao(8, "veiculo", 0.8, "baixa", "observacao_visual", (i * 10, 0, i * 10 + 8, 8), "car")
        for i in range(quantidade)
    ]


def _alagamento(confianca: float) -> list[Deteccao]:
    return [Deteccao(1, "alagamento", confianca, "critica", "alagamento", (0, 0, 50, 50), "flood")]


class _Coletor(logging.Handler):
    """Guarda as mensagens de log do sistema para entrarem na saída do replay."""

    def __init__(self) -> None:
        super().__init__(logging.INFO)
        self.linhas: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        # A data do frame muda a cada execução, então vira um marcador fixo.
        mensagem = _DATA_HTTP.sub("<data do frame>", record.getMessage())
        self.linhas.append(f"    log {record.levelname}: {mensagem}")


class _Replay:
    def __init__(self, pilha: ExitStack) -> None:
        self.pilha = pilha
        self.saida: list[str] = []
        self.coletor = _Coletor()

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

        evidencias = Path(pilha.enter_context(tempfile.TemporaryDirectory(prefix="motsp-replay-")))
        trocas = [
            (live_detection, "SessionLocal", lambda: _sessao()),
            (flood_detection, "SessionLocal", lambda: _sessao()),
            (detection_events, "_EVIDENCIAS_DIR", evidencias),
            (detection_events, "annotate_evidence", lambda conteudo, _d: (conteudo, 640, 360)),
            (flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: {"disponivel": False}),
            (flood_detection, "obter_aviso_ativo", lambda: {"disponivel": False}),
            (flood_detection, "indice_historico", lambda _lat, _lon: (0.0, "sem histórico")),
        ]
        for modulo, nome, valor in trocas:
            pilha.enter_context(mock.patch.object(modulo, nome, valor))
        for nome, valor in LIMIARES.items():
            pilha.enter_context(mock.patch.object(settings, nome, valor))

        for nome in ("app.services.live_detection", "app.services.flood_detection"):
            logger = logging.getLogger(nome)
            pilha.callback(logger.setLevel, logger.level)
            logger.setLevel(logging.INFO)
            logger.addHandler(self.coletor)
            pilha.callback(logger.removeHandler, self.coletor)

    def escrever(self, texto: str) -> None:
        self.saida.extend(self.coletor.linhas)
        self.coletor.linhas.clear()
        self.saida.append(texto)

    def _novos_eventos(self, antes: set[int]) -> list[Evento]:
        self.sessao.expire_all()
        return [e for e in self.sessao.query(Evento).order_by(Evento.id) if e.id not in antes]

    def _ids(self) -> set[int]:
        return {i for (i,) in self.sessao.query(Evento.id)}

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

    def resultado(self, novos: list[Evento]) -> None:
        self.saida.extend(self.coletor.linhas)
        self.coletor.linhas.clear()
        if not novos:
            self.saida.append("    resultado: nenhum evento criado")
        for evento in novos:
            self.saida.append(self._descrever(evento))

    def transito(self, rotulo: str, veiculos: int, tomtom: dict, lat: float, cooldown: dict | None = None) -> None:
        consultas: list[int] = []

        def _tomtom(_lat, _lon):
            consultas.append(1)
            return tomtom

        self.escrever(rotulo)
        antes = self._ids()
        with mock.patch.object(live_detection, "detectar_imagem_real", lambda _c, _t: _veiculos(veiculos)), \
             mock.patch.object(live_detection, "obter_fluxo_transito", _tomtom):
            live_detection._processar_frame(
                b"frame-sintetico", lat, -46.63, settings.yolo_threshold,
                {} if cooldown is None else cooldown, f"câmera sintética {lat}",
            )
        self.saida.append(f"    TomTom consultada: {'sim' if consultas else 'não'}")
        self.resultado(self._novos_eventos(antes))

    def alagamento(self, rotulo: str, confianca: float, lat: float, chuva=None, inmet=None, historico=0.0) -> None:
        clima = {"disponivel": True, "chuva_mm": chuva} if chuva is not None else {"disponivel": False}
        aviso = (
            {"disponivel": True, "menciona_alagamento": True, "severidade_indice": inmet}
            if inmet is not None else {"disponivel": False}
        )
        self.escrever(rotulo)
        antes = self._ids()
        with mock.patch.object(flood_detection, "detectar_incidentes_imagem", lambda _c, _t: _alagamento(confianca)), \
             mock.patch.object(flood_detection, "obter_condicoes_atuais", lambda _lat, _lon: clima), \
             mock.patch.object(flood_detection, "obter_aviso_ativo", lambda: aviso), \
             mock.patch.object(flood_detection, "indice_historico", lambda _lat, _lon: (historico, f"índice {historico:g}")):
            flood_detection._processar_frame(
                b"frame-sintetico-alagamento", lat, -46.60, settings.gx_yolo_incident_conf, {}, f"câmera sintética {lat}",
            )
        self.resultado(self._novos_eventos(antes))

    def camera(self, rotulo: str, frames: list[tuple[bytes, int]]) -> None:
        """Simula a câmera mandando uma sequência de frames.

        Cada frame é (conteúdo, idade em segundos informada no Last-Modified).
        """
        processados: list[bytes] = []
        fila = list(frames)

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
                return _Resposta(*fila.pop(0))

        def _esperar(_segundos):
            if not fila:
                live_detection._stop_event.set()

        self.escrever(rotulo)
        live_detection._stop_event.clear()
        with mock.patch.object(httpx, "Client", _Cliente), \
             mock.patch.object(live_detection, "_processar_frame", lambda conteudo, *_a: processados.append(conteudo)), \
             mock.patch.object(live_detection._stop_event, "wait", _esperar):
            live_detection._loop("http://camera-sintetica/1.jpg", -23.0, -46.0, 1.0, 0.45, "câmera sintética")
        live_detection._stop_event.clear()
        self.saida.extend(self.coletor.linhas)
        self.coletor.linhas.clear()
        self.saida.append(f"    frames recebidos: {len(frames)}, enviados ao YOLO: {len(processados)}")

    def expiracao(self, rotulo: str, minutos: list[int]) -> None:
        self.escrever(rotulo)
        agora = datetime.now(UTC).replace(tzinfo=None)
        criados = []
        for i, atras in enumerate(minutos):
            local = Localizacao(latitude=-22.0 - i * 0.01, longitude=-45.0)
            self.sessao.add(local)
            self.sessao.flush()
            evento = Evento(
                titulo="Evento sintético", tipo="transito", severidade="baixa", status="em_analise",
                localizacao_id=local.id, detectado_em=agora - timedelta(minutes=atras),
            )
            self.sessao.add(evento)
            self.sessao.flush()
            criados.append((evento.id, atras))
        self.sessao.commit()
        with mock.patch.object(event_retention, "_publicar_remocoes", lambda _ids: None):
            removidos = event_retention.purgar_eventos_expirados(self.sessao)
        self.sessao.expire_all()
        for evento_id, atras in criados:
            existe = self.sessao.get(Evento, evento_id) is not None
            self.saida.append(f"    evento detectado há {atras} min: {'mantido' if existe else 'removido'}")
        self.saida.append(f"    total removido: {removidos}")


def executar() -> list[str]:
    with ExitStack() as pilha:
        r = _Replay(pilha)
        r.saida.append("MotSP replay sintético")
        r.saida.append(
            "limiares: " + ", ".join(f"{k}={v}" for k, v in LIMIARES.items())
        )

        r.saida.append("")
        r.saida.append("== Trânsito ==")
        r.transito("[T1] 18 veículos, TomTom fora do ar", 18, _SEM_TOMTOM, -23.50)
        r.transito("[T2] 13 veículos, TomTom diz trecho fluindo (índice 1,0)", 13,
                   {"disponivel": True, "indice_congestionamento": 1.0}, -23.51)
        r.transito("[T3] 6 veículos, TomTom confirma lentidão (índice 8,0)", 6,
                   {"disponivel": True, "indice_congestionamento": 8.0}, -23.52)
        r.transito("[T4] 6 veículos, TomTom fora do ar", 6, _SEM_TOMTOM, -23.53)
        r.transito("[T5] 3 veículos, abaixo do piso", 3,
                   {"disponivel": True, "indice_congestionamento": 9.0}, -23.54)
        cooldown: dict[str, float] = {}
        r.transito("[T6] 18 veículos numa câmera nova", 18, _SEM_TOMTOM, -23.55, cooldown)
        r.transito("[T7] mesma câmera de T6 logo em seguida (dentro dos 30 min)", 18, _SEM_TOMTOM, -23.55, cooldown)

        r.saida.append("")
        r.saida.append("== Alagamento ==")
        r.alagamento("[A1] YOLO vê alagamento (0,81) sem chuva, aviso nem histórico", 0.81, -23.60)
        r.alagamento("[A2] YOLO vê alagamento (0,81) com chuva de 30 mm/h, aviso INMET 9,5 e via que alaga sempre",
                     0.81, -23.61, chuva=30.0, inmet=9.5, historico=9.0)

        r.saida.append("")
        r.saida.append("== Câmera ==")
        r.camera("[C1] câmera travada: frame com 10 min de idade", [(b"frame-velho", 600)])
        r.camera("[C2] frame novo (1 min) chega três vezes igual e depois muda",
                 [(b"frame-a", 60), (b"frame-a", 60), (b"frame-a", 60), (b"frame-b", 60)])

        r.saida.append("")
        r.saida.append("== Expiração ==")
        r.expiracao("[E1] eventos detectados há 50 e há 10 min (janela de 45 min)", [50, 10])
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
