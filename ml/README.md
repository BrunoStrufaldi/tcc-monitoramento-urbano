# Módulo YOLO (visão computacional)

Prova de conceito de detecção de eventos urbanos via visão computacional.

## Estrutura

```
ml/
├── detector.py              # Detector YOLO real + rota de demonstração separada
├── train_incident_model.py  # Treina o detector de alagamento (1 classe)
├── collect_negatives.py     # Coleta frames das câmeras CET-SP como negativos de treino
├── models/                  # Pesos locais (yolo11m.pt trânsito / yolo11s.pt base-treino / gx-incident.pt alagamento)
└── README.md
```

## Classes Detectáveis

| ID | Classe | Severidade | Tipo |
|----|--------|------------|------|
| 1 | alagamento | critica | clima |
| 2 | transito | media | mobilidade |

(Havia também buraco (0), lixo (3), incêndio (4), construção irregular (5),
`arvore_caida` (6) e vazamento (7) — todas removidas por decisão do grupo de
focar o escopo do TCC só em alagamento e trânsito, os dois tipos com detector
de verdade rodando contínuo. Os IDs não foram reaproveitados.)

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
`ml/models/yolo11m.pt` (YOLO11 COCO), que reconhece veículos e os normaliza
como o evento urbano `transito`. (Era `yolo11n`; `m` detecta carro
pequeno/distante/noturno bem melhor — ver comentário em `detector.py`.)

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
(padrão `ml/models/gx-incident.pt`). Com `GX_ALAGAMENTO_MONITORAR_CATALOGO=true`,
`backend/app/services/flood_detection.py` roda esse modelo direto nas 11
câmeras públicas da CET (mesmo padrão do `live_detection.py` de trânsito,
inclusive a checagem de frame desatualizado) — sem o modelo dedicado
configurado, o loop sobe mas cada frame é descartado silenciosamente.

(Havia também um caminho reativo, disparado por ocorrências em lote do
GeoSampa em `context_monitor.py` — removido junto com o GeoSampa, por
decisão do grupo de manter só dado em tempo real.)

O peso é treinado com **uma classe só: `alagamento`**. A classe `arvore_caida`
saiu do escopo do TCC — o app já descartava (não tem entrada em
`CLASSES_URBANAS`, `ml/detector.py`) e no treino ela só desbalanceava o dataset
(~5% das instâncias) e confundia o classificador.

### Por que o retreino: falsos positivos

O peso anterior alucinava caixa de `alagamento` em cena seca / rua molhada à
noite / no nada. Causa raiz medida em `ml/runs/incident/`: o dataset de treino
tinha **6 imagens negativas em 2470** — o modelo nunca viu uma via sem
alagamento e aprendeu que "toda imagem tem alagamento em algum canto" (matriz
de confusão: 98% dos falsos positivos caíam em `alagamento`). O
`train_incident_model.py` agora ingere negativos explícitos via `--negatives`
e avisa se ficarem abaixo de 20% do treino.

### Treinar (requer `pip install -r backend/requirements-yolo.txt`; `ROBOFLOW_API_KEY` só para inspect/download)

```bash
# 1. Ver versões de um dataset público do Roboflow Universe
python ml/train_incident_model.py inspect --workspace testingforyolo --project floods-by-agroudy

# 2. Baixar um ou mais datasets de alagamento em formato YOLOv8
python ml/train_incident_model.py download --workspace testingforyolo --project floods-by-agroudy --version 2 --out ml/datasets/flood

# 3. Coletar negativos: frames das câmeras CET-SP em tempo seco/noite/chuva-sem-alagar.
#    Rode em horários variados ao longo de alguns dias e revise a pasta depois,
#    apagando qualquer frame com água acumulada de verdade.
python ml/collect_negatives.py --hours 12          # ou sem --hours: roda até Ctrl+C
python ml/collect_negatives.py --cameras 22,23,180 --interval 30

# 4. Fundir tudo num dataset de 1 classe (--flood repetível; '*' = todas as classes da fonte viram alagamento)
python ml/train_incident_model.py merge \
  --flood ml/datasets/flood --flood-classes "*" \
  --negatives ml/datasets/negativos_cet \
  --out ml/datasets/incidentes --limpar

# 5. Treinar (GPU CUDA por padrão; base yolo11s, early stopping em 30 épocas)
python ml/train_incident_model.py train --data ml/datasets/incidentes/data.yaml --epochs 120
```

O `best.pt` é copiado para `ml/models/gx-incident.pt` (o peso anterior vira
`gx-incident-anterior.pt`). Ative apontando `GX_YOLO_INCIDENT_MODEL` pra esse
caminho (já é o padrão) e reinicie o backend. Antes de confiar, rode o detector
num punhado de frames CET reais e confira se a caixa fantasma sumiu; se ainda
houver, suba `yolo_threshold` (0.45 → ~0.6).
