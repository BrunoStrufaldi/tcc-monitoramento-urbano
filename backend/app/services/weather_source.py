"""Fonte climática externa para enriquecer o centro operacional."""

import json
from urllib.parse import urlencode
from urllib.request import urlopen


def obter_condicoes_atuais(latitude: float, longitude: float) -> dict:
    """Consulta as condições atuais do Open-Meteo para uma coordenada."""
    query = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,precipitation,rain,wind_speed_10m,weather_code",
        "timezone": "America/Sao_Paulo",
    })
    url = "https://api.open-meteo.com/v1/forecast?" + query
    try:
        with urlopen(url, timeout=6) as response:  # nosec B310 - URL fixa e pública
            payload = json.load(response)
    except Exception as exc:
        return {"disponivel": False, "fonte": "Open-Meteo", "erro": str(exc)}

    current = payload.get("current", {})
    return {
        "disponivel": True,
        "fonte": "Open-Meteo",
        "atualizado_em": current.get("time"),
        "latitude": payload.get("latitude", latitude),
        "longitude": payload.get("longitude", longitude),
        "temperatura_c": current.get("temperature_2m"),
        "precipitacao_mm": current.get("precipitation"),
        "chuva_mm": current.get("rain"),
        "vento_kmh": current.get("wind_speed_10m"),
        "codigo_tempo": current.get("weather_code"),
    }


def obter_qualidade_do_ar(latitude: float, longitude: float) -> dict:
    """Consulta índices atuais de qualidade do ar na API pública Open-Meteo."""
    query = urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "pm2_5,pm10,us_aqi,european_aqi",
        "timezone": "America/Sao_Paulo",
    })
    url = "https://air-quality-api.open-meteo.com/v1/air-quality?" + query
    try:
        with urlopen(url, timeout=6) as response:  # nosec B310 - URL fixa e pública
            payload = json.load(response)
    except Exception as exc:
        return {"disponivel": False, "fonte": "Open-Meteo Air Quality", "erro": str(exc)}

    current = payload.get("current", {})
    return {
        "disponivel": True,
        "fonte": "Open-Meteo Air Quality",
        "atualizado_em": current.get("time"),
        "latitude": payload.get("latitude", latitude),
        "longitude": payload.get("longitude", longitude),
        "aqi_us": current.get("us_aqi"),
        "aqi_europeu": current.get("european_aqi"),
        "pm2_5": current.get("pm2_5"),
        "pm10": current.get("pm10"),
    }
