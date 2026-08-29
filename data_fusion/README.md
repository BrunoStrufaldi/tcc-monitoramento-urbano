# Módulo Data Fusion

Calcula a **confiabilidade** de um evento urbano combinando três dimensões:

| Dimensão | Peso | Origem dos dados |
|----------|------|------------------|
| **IA** | 40% | `evidencias_visuais` (YOLO, confiança, modelo) |
| **Clima** | 30% | `dados_contextuais` com `categoria = clima` |
| **Fonte oficial** | 30% | `fontes_dados` (`api`, `sensor`, etc.) |

Para eventos de **alagamento**, a dimensão de clima combina chuva (Open-Meteo),
aviso ativo do INMET e um **prior espacial estático**: o histórico de alagamento
da via (`historico_alagamento.py`, a partir de `data/pontos_alagamento_sp.json`,
lookup local). O histórico não é dimensão isolada — só reforça quando já há sinal
ao vivo e derruba a pontuação quando não há chuva/aviso e a via não tem histórico
(falso positivo provável do modelo de incidentes).

## API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/fusion/eventos/{id}/confiabilidade` | Calcula sem gravar |
| POST | `/fusion/eventos/{id}/recalcular?persistir=true` | Grava em `eventos.confianca` |
| POST | `/fusion/recalcular-todos` | Processa lote |

## Teste

```bash
python -m data_fusion.test_fusion
python -m data_fusion.test_historico_alagamento
```
