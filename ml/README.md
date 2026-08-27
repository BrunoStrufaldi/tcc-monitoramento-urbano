# Módulo YOLO (visão computacional)

Prova de conceito de detecção de eventos urbanos via visão computacional.

## Estrutura

```
ml/
├── detector.py     # Detector YOLO real + rota de demonstração separada
├── models/         # Pesos locais (yolo11n.pt ou pesos urbanos GX)
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
| 7 | vazamento | alta | infraestrutura |

(Havia uma classe 6, `arvore_caida`, removida por decisão do grupo de tirar
esse tipo do escopo do TCC — o ID não foi reaproveitado.)

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

O GX já usa inferência YOLO real em `POST /deteccao/imagem`. O peso padrão é
`ml/models/yolo11n.pt` (YOLO11 COCO), que reconhece veículos e os normaliza
como o evento urbano `transito`.

Para reconhecer as oito classes urbanas específicas, substitua o peso padrão:

```python
from ultralytics import YOLO

model = YOLO("ml/models/yolov8n.pt")

def detectar_imagem(caminho: str):
    results = model(caminho)
    # Mapear results[0].boxes para Deteccao...
```

## YOLO real no GX

O endpoint `POST /deteccao/imagem` executa inferência real e não usa dados simulados. Para habilitá-lo na máquina de processamento:

```bash
cd backend
venv\Scripts\python -m pip install -r requirements-yolo.txt
set GX_YOLO_MODEL=ml/models/gx-urban.pt
uvicorn app.main:app --reload
```

`GX_YOLO_MODEL` deve apontar para pesos Ultralytics treinados com as classes urbanas do GX. O modelo COCO padrão registra veículos apenas como `observacao_visual`; presença de carro não significa congestionamento. Alagamento, buraco e os demais incidentes precisam de pesos especializados e validação. Verifique `GET /deteccao/status` antes de enviar imagens.

Os uploads são temporários, aceitam PNG/JPG/WEBP de até 10 MB e são removidos assim que a inferência termina. A rota `POST /deteccao/simular` permanece separada apenas para demonstração e testes.

## Modelo dedicado de incidentes (alagamento)

O peso COCO padrão não reconhece essa classe. Em vez de substituir o modelo
global (o que quebraria a contagem de veículos do trânsito ao vivo), o GX
carrega um **segundo modelo**, separado, só para isso: `GX_YOLO_INCIDENT_MODEL`
(padrão `ml/models/gx-incident.pt`). Quando ele está disponível e detecta a
classe esperada numa câmera próxima de uma ocorrência GeoSampa, isso vira
confirmação visual direta em `context_monitor.py`; sem ele, o sistema
continua no modo sinal indireto (COCO, teto de confiança 0.5) como hoje.

O peso atual foi treinado com duas classes (alagamento e árvore caída — passo
a passo abaixo, mantido por precisão histórica), mas o app não usa mais a
classe de árvore caída desde que o grupo decidiu tirar esse tipo do escopo do
TCC: ela não tem entrada em `CLASSES_URBANAS` (`ml/detector.py`), então
qualquer detecção dela é descartada antes de virar evento.

Para treinar esse peso, use `ml/train_incident_model.py` (requer
`pip install -r backend/requirements-yolo.txt` e uma API key gratuita do
Roboflow em `ROBOFLOW_API_KEY`):

```bash
# 1. Ver as versões disponíveis de um dataset público do Roboflow Universe
python ml/train_incident_model.py inspect --workspace testingforyolo --project floods-by-agroudy

# 2. Baixar os dois datasets (alagamento e árvore caída) em formato YOLOv8
python ml/train_incident_model.py download --workspace testingforyolo --project floods-by-agroudy --version 1 --out ml/datasets/flood
python ml/train_incident_model.py download --workspace fallen-tree-on-roads --project fallen-trees-on-road --version 2 --out ml/datasets/tree

# 3. Fundir num único conjunto de 2 classes (nomes de classe reais confirmados no passo 2)
python ml/train_incident_model.py merge --flood ml/datasets/flood --flood-classes "flood" --tree ml/datasets/tree --tree-classes "fallen tree" --out ml/datasets/incidentes

# 4. Treinar (usa GPU CUDA por padrão; ~80 épocas em yolo11n)
python ml/train_incident_model.py train --data ml/datasets/incidentes/data.yaml --epochs 80
```

O resultado é copiado para `ml/models/gx-incident.pt`. Ative apontando
`GX_YOLO_INCIDENT_MODEL` pra esse caminho (já é o padrão) e reinicie o backend.
