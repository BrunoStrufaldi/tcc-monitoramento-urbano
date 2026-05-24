# Módulo Data Fusion

Calcula a **confiabilidade** de um evento urbano combinando três dimensões:

| Dimensão | Peso | Origem dos dados |
|----------|------|------------------|
| **IA** | 40% | `evidencias_visuais` (YOLO, confiança, modelo) |
| **Clima** | 30% | `dados_contextuais` com `categoria = clima` |
| **Fonte oficial** | 30% | `fontes_dados` (`api`, `sensor`, etc.) |

## Fórmula

```
confiabilidade = (score_ia × 0,40) + (score_clima × 0,30) + (score_fonte × 0,30)
```

Níveis: **alta** (≥ 0,80), **média** (≥ 0,55), **baixa** (&lt; 0,55).

## Uso standalone (Python)

```python
from data_fusion import calcular_confiabilidade
from data_fusion.models import DadoClima, EvidenciaIA, EventoFusionInput, FonteInfo

entrada = EventoFusionInput(
    evento_id=1,
    tipo="alagamento",
    evidencias_ia=[],
    dados_clima=[DadoClima(chave="precipitacao_mm_h", valor_numerico=45.2)],
    fonte=FonteInfo(tipo="api", nome="API Prefeitura"),
)
resultado = calcular_confiabilidade(entrada)
print(resultado.confiabilidade, resultado.nivel)
```

## API FastAPI

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/fusion/eventos/{id}/confiabilidade` | Calcula sem gravar |
| POST | `/fusion/eventos/{id}/recalcular?persistir=true` | Calcula e grava em `eventos.confianca` |
| POST | `/fusion/recalcular-todos` | Processa lote |

## Teste local

Na raiz do projeto:

```bash
python -m data_fusion.test_fusion
```

## Estrutura

```
data_fusion/
├── models.py    # Entradas e saída
├── scores.py    # Pontuação por dimensão
├── fusion.py    # Motor de fusão
└── test_fusion.py
```
