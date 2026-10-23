# Treino do modelo de alagamento

[← voltar ao README](../README.md#documentação)

## 16. Treino do modelo de alagamento

O `ml/train_incident_model.py` treina o `gx-incident.pt` com uma classe só: `alagamento`.
A classe `arvore_caida` saiu do escopo, e no treino ela só desequilibrava o dataset (era
uns 5% das marcações) e confundia o modelo.

### O problema que motivou o retreino

O modelo anterior via `alagamento` em pista seca, em rua molhada à noite e às vezes em
lugar nenhum. A causa, medida em `ml/runs/incident/`, era que o dataset tinha só 6 imagens
sem alagamento em 2.470. O modelo nunca tinha visto uma via seca e aprendeu que "toda
imagem tem alagamento em algum canto": 98% dos falsos positivos estavam nessa classe na
matriz de confusão.

Hoje o `train_incident_model.py` recebe imagens sem alagamento pelo `--negatives` e avisa
se elas forem menos de 20% do treino.

### Pipeline

```bash
# 0) dependências (só na máquina de treino)
pip install -r backend/requirements-yolo.txt      # ROBOFLOW_API_KEY só para inspect/download

# 1) ver as versões de um dataset público do Roboflow Universe
python ml/train_incident_model.py inspect --workspace testingforyolo --project floods-by-agroudy

# 2) baixar no formato YOLOv8
python ml/train_incident_model.py download \
  --workspace testingforyolo --project floods-by-agroudy --version 2 --out ml/datasets/flood

# 3) coletar imagens SEM alagamento das câmeras da CET (dia seco, noite, chuva sem alagar).
#    Rode em horários diferentes ao longo de alguns dias e depois confira a pasta,
#    apagando as imagens que tiverem água acumulada de verdade.
python ml/collect_negatives.py --hours 12                    # sem --hours: roda até Ctrl+C
python ml/collect_negatives.py --cameras 22,23,180 --interval 30

# 4) juntar num dataset de 1 classe (--flood pode repetir; '*' = todas as classes viram alagamento)
python ml/train_incident_model.py merge \
  --flood ml/datasets/flood --flood-classes "*" \
  --negatives ml/datasets/negativos_cet \
  --out ml/datasets/incidentes --limpar

# 5) treinar (GPU por padrão; base yolo11s, para sozinho depois de 30 épocas sem melhora)
python ml/train_incident_model.py train --data ml/datasets/incidentes/data.yaml --epochs 120
```

O `best.pt` é copiado para `ml/models/gx-incident.pt`, e o modelo anterior vira
`gx-incident-anterior.pt`. Reinicie o backend para carregar o novo.

Antes de confiar no modelo novo, rode o detector em algumas imagens reais da CET e
confira se as caixas falsas sumiram. Se ainda aparecerem, aumente o
`GX_YOLO_INCIDENT_CONF` (de 0,45 para uns 0,6, ou mais).
