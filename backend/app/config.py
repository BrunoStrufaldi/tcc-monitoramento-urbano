from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./gx.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500,http://localhost:8080"
    auth_secret_key: str | None = None
    auth_token_expire_minutes: int = 60
    auth_allow_self_registration: bool = False
    auth_bootstrap_admin_username: str | None = None
    auth_bootstrap_admin_password: str | None = None
    yolo_threshold: float = 0.45
    yolo_max_fps: int = 3
    yolo_max_frame_bytes: int = 1_500_000
    yolo_max_frame_width: int = 1280
    yolo_cooldown_seconds: int = 20
    gx_camera_snapshot_url: str | None = None
    gx_camera_latitude: float | None = None
    gx_camera_longitude: float | None = None
    gx_live_detection_interval_seconds: float = 5.0
    gx_monitoramento_ativo: bool = False
    gx_transito_min_veiculos: int = 20
    gx_alerta_cooldown_seconds: float = 1800.0
    gx_transito_monitorar_catalogo: bool = False
    gx_alagamento_monitorar_catalogo: bool = False
    gx_camera_frescor_maximo_segundos: float = 300.0
    # "Tempo real" é literal: eventos (qualquer status) só aparecem e só ficam
    # no banco enquanto detectados dentro desta janela. Mantido acima do
    # cooldown de alerta para não abrir buracos entre uma detecção e a próxima.
    gx_evento_janela_minutos: int = 45
    # Confiabilidade (Data Fusion) a partir da qual um evento "em_analise" é
    # promovido automaticamente para "ativo".
    gx_fusion_auto_ativo_min: float = 0.75

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
