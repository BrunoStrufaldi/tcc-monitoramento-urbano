from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./gx.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    # Só é preciso se o painel for aberto a partir de outro endereço.
    cors_origins: str = ""
    # A própria API serve o painel. Se desligar, "/" mostra só o status da API.
    gx_serve_frontend: bool = True
    yolo_threshold: float = 0.45
    # Modelos do YOLO. Caminhos relativos partem da raiz do projeto.
    # O modelo de veículos foi ajustado com imagens das câmeras da CET.
    gx_yolo_model: str = "ml/models/gx-veiculos.pt"
    gx_yolo_incident_model: str = "ml/models/gx-incident.pt"
    gx_yolo_imgsz: int = 1280
    gx_yolo_tta: bool = True
    gx_yolo_max_concorrencia: int = 2
    # Confiança mínima do modelo de alagamento. É mais alta que a de veículos
    # porque, abaixo disso, ele confundia pista seca com alagamento.
    gx_yolo_incident_conf: float = 0.6
    gx_camera_snapshot_url: str | None = None
    gx_camera_latitude: float | None = None
    gx_camera_longitude: float | None = None
    gx_live_detection_interval_seconds: float = 5.0
    gx_monitoramento_ativo: bool = False
    # Quantidade de veículos que já indica trânsito. Mesmo assim, a TomTom
    # ainda pode recusar se a via estiver fluindo.
    gx_transito_min_veiculos: int = 12
    # Abaixo disso a imagem é ignorada. Entre este valor e o de cima, o evento
    # só é criado se a TomTom confirmar a lentidão. Isso ajuda à noite, quando a
    # imagem escura faz o YOLO contar menos carros.
    gx_transito_min_veiculos_corroborado: int = 4
    # A partir dessa quantidade o evento é criado sem consultar a TomTom.
    gx_transito_min_veiculos_confirmado: int = 16
    # Índice mínimo de lentidão da TomTom para confirmar o trânsito.
    gx_transito_tomtom_indice_minimo: float = 3.0
    gx_alerta_cooldown_seconds: float = 1800.0
    # Tempo de espera depois que a TomTom recusa um evento. É curto para não
    # deixar a câmera parada muito tempo, e também limita as consultas à API.
    gx_transito_veto_cooldown_seconds: float = 600.0
    gx_transito_monitorar_catalogo: bool = False
    gx_alagamento_monitorar_catalogo: bool = False
    gx_camera_frescor_maximo_segundos: float = 300.0
    # Por quanto tempo um evento fica no painel depois da última detecção.
    gx_evento_janela_minutos: int = 45
    # Confiabilidade a partir da qual um evento em análise passa para ativo.
    gx_fusion_auto_ativo_min: float = 0.77
    # Chave da TomTom. Ela precisa ser lida aqui para que o valor do .env chegue
    # até o serviço.
    tomtom_api_key: str | None = None

    @field_validator("database_url")
    @classmethod
    def usar_sqlite_quando_mysql_for_exemplo(cls, value: str) -> str:
        """Usa o SQLite se o .env ainda estiver com a senha de exemplo do MySQL."""
        if "usuario:senha@" in value or "root:senha@" in value:
            return "sqlite:///./gx.db"
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
