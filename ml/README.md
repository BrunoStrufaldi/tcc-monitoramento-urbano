# Módulo YOLO (visão computacional)

Prova de conceito de detecção de eventos urbanos via visão computacional.

## Estrutura

```
ml/
├── detector.py     # Detector simulado (8 classes urbanas)
└── README.md
```

## Classes Detectáveis

| ID | Classe | Severidade | Tipo |
|----|--------|------------|------|
| 0 | buraco | alta | infraestrutura |
| 1 | alagamento | critica | clima |
| 2 | transito | media | mobilidade |
| 3 | lixo | baixa | meio_ambiente |
| 4 | incendio | critica | seguranca |
| 5 | construcao_irregular | alta | urbanismo |
| 6 | arvore_caida | media | infraestrutura |
| 7 | vazamento | alta | infraestrutura |

## Uso

### Simulação simples

```python
from ml.detector import detectar_imagem

deteccoes = detectar_imagem("foto.jpg", num_deteccoes=2)
for d in deteccoes:
    print(f"{d.nome} ({d.confianca:.1%}) — {d.severidade}")
```

### Via API

```bash
# Listar classes
curl http://localhost:8000/deteccao/classes

# Simular detecção
curl -X POST http://localhost:8000/deteccao/simular

# Upload de imagem
curl -X POST http://localhost:8000/deteccao/imagem -F "file=@foto.jpg"
```

## Integração com YOLO real

Para usar YOLO real, substitua `detectar_imagem()` em `detector.py`:

```python
from ultralytics import YOLO

model = YOLO("ml/models/yolov8n.pt")

def detectar_imagem(caminho: str):
    results = model(caminho)
    # Mapear results[0].boxes para Deteccao...
```
