# Módulo Data Fusion

Calcula a **confiabilidade** de um evento urbano combinando três dimensões:

| Dimensão | Peso | Origem dos dados |
|----------|------|------------------|
| **IA** | 40% | `evidencias_visuais` (YOLO, confiança, modelo) |
| **Clima** | 30% | `dados_contextuais` com `categoria = clima` |
| **Fonte oficial** | 30% | `fontes_dados` (`api`, `sensor`, etc.) |

## API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/fusion/eventos/{id}/confiabilidade` | Calcula sem gravar |
| POST | `/fusion/eventos/{id}/recalcular?persistir=true` | Grava em `eventos.confianca` |
| POST | `/fusion/recalcular-todos` | Processa lote |

## Teste

```bash
python -m data_fusion.test_fusion
```
