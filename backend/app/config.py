from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./gx.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080"
    yolo_threshold: float = 0.45
    # Confiança mínima só para o modelo de incidentes (alagamento). Mais alta que
    # a de veículos de propósito: enquanto o peso de alagamento não é retreinado
    # com negativos, ele dispara caixa em cena seca com score baixo — 0.6 corta a
    # maior parte desses falsos positivos sem endurecer a contagem de trânsito.
    gx_yolo_incident_conf: float = 0.6
    yolo_max_fps: int = 3
    yolo_max_frame_bytes: int = 1_500_000
    yolo_max_frame_width: int = 1280
    yolo_cooldown_seconds: int = 20
    gx_camera_snapshot_url: str | None = None
    gx_camera_latitude: float | None = None
    gx_camera_longitude: float | None = None
    gx_live_detection_interval_seconds: float = 5.0
    gx_monitoramento_ativo: bool = False
    # Nº de veículos num mesmo frame para o sistema AVALIAR congestionamento —
    # abaixo disso nem consulta a TomTom. Medido nas câmeras CET (frame pega
    # trecho curto de via): rush da tarde dá 16-24, noite 15-18. 12 porque o YOLO
    # subconta fila acumulada ao fundo (carro pequeno/distante) e a contagem pega
    # os dois sentidos + fila da transversal; na faixa 12..confirmado a TomTom
    # arbitra se vira evento (ver _avaliar_gatilho_transito em live_detection).
    gx_transito_min_veiculos: int = 12
    # Piso absoluto: abaixo disto o frame nem é avaliado (nem a TomTom é
    # consultada). Entre este piso e gx_transito_min_veiculos a contagem sozinha
    # NÃO cria evento — só cria se a TomTom corroborar lentidão no trecho. É o
    # caso do rush noturno: o JPEG escuro da câmera pública derruba o score do
    # YOLO e a contagem fica em 4..7 numa via comprovadamente parada. Abaixo de
    # 4 veículos não há aglomeração visível que sustente a evidência anexada ao
    # evento, por mais lento que a TomTom diga que o trecho está.
    gx_transito_min_veiculos_corroborado: int = 4
    # Contagem a partir da qual o evento é criado mesmo sem a TomTom confirmar —
    # frame muito cheio é sinal forte por si só.
    gx_transito_min_veiculos_confirmado: int = 16
    # Na faixa gx_transito_min_veiculos .. gx_transito_min_veiculos_confirmado, a
    # TomTom precisa reportar índice de congestionamento >= isto para o evento
    # ser criado. Abaixo (trecho a >= ~70% da velocidade livre) ela está dizendo
    # "via fluindo" e o evento é descartado. Sem TOMTOM_API_KEY, a faixa cai no
    # comportamento antigo (decisão só por contagem).
    gx_transito_tomtom_indice_minimo: float = 3.0
    gx_alerta_cooldown_seconds: float = 1800.0
    # Silêncio após a TomTom VETAR o frame (trecho fluindo). Curto de propósito:
    # o cooldown longo acima só vale quando um evento nasce de fato, senão um
    # veto às 19h00 calaria a câmera até 19h30 mesmo com a via travando no meio
    # do caminho. Também é o teto de consumo da TomTom: uma consulta por câmera
    # a cada 10 min = ~1.4k chamadas/dia nas 10 câmeras, dentro do plano free.
    gx_transito_veto_cooldown_seconds: float = 600.0
    gx_transito_monitorar_catalogo: bool = False
    gx_alagamento_monitorar_catalogo: bool = False
    gx_camera_frescor_maximo_segundos: float = 300.0
    # "Tempo real" é literal: eventos (qualquer status) só aparecem e só ficam
    # no banco enquanto detectados dentro desta janela. Mantido acima do
    # cooldown de alerta para não abrir buracos entre uma detecção e a próxima.
    gx_evento_janela_minutos: int = 45
    # Confiabilidade (Data Fusion) a partir da qual um evento "em_analise" é
    # promovido automaticamente para "ativo".
    gx_fusion_auto_ativo_min: float = 0.80
    # Chave da TomTom Traffic API. Precisa passar por aqui, e não por
    # os.getenv direto no serviço: o .env é lido pelo pydantic-settings, que
    # popula este objeto mas NÃO o os.environ do processo. Enquanto o serviço
    # lia os.getenv, a chave configurada no .env nunca chegava nele e toda
    # consulta caía em "TOMTOM_API_KEY não configurada" em silêncio — o
    # start.ps1 sobe o uvicorn direto, sem exportar variável nenhuma.
    tomtom_api_key: str | None = None

    @field_validator("database_url")
    @classmethod
    def usar_sqlite_quando_mysql_for_exemplo(cls, value: str) -> str:
        """Evita que credenciais de exemplo deixem a API local inutilizável."""
        if "usuario:senha@" in value or "root:senha@" in value:
            return "sqlite:///./gx.db"
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
