"""Módulo de fusão de dados — confiabilidade de eventos urbanos."""

from data_fusion.fusion import calcular_confiabilidade
from data_fusion.models import EventoFusionInput, ResultadoFusao

__all__ = ["calcular_confiabilidade", "EventoFusionInput", "ResultadoFusao"]
