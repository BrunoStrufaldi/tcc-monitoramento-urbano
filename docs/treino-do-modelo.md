# Treino do modelo de alagamento

[← voltar ao README](../README.md#documentação)

## 16. Treino do modelo de alagamento

`ml/train_incident_model.py` — o peso `gx-incident.pt` é treinado com **uma classe só**:
`alagamento`. `arvore_caida` saiu do escopo; no treino ela só desbalanceava o dataset
(~5% das instâncias) e confundia o classificador.

### O problema que motivou o retreino

O peso anterior alucinava caixa de `alagamento` em cena seca, rua molhada à noite, e às vezes
no nada. Causa raiz medida em `ml/runs/incident/`: o dataset tinha **6 imagens negativas em
2.470**. O modelo nunca viu uma via sem alagamento e aprendeu que "toda imagem tem alagamento
em algum canto" — 98% dos falsos positivos caíam nessa classe na matriz de confusão.

`train_incident_model.py` hoje ingere negativos explícitos via `--negatives` e **avisa** se
ficarem abaixo de 20% do treino.

### Pipeline

```bash
# 0) dependências (só na máquina de treino)
pip install -r backend/requirements-yolo.txt      # ROBOFLOW_API_KEY só para inspect/download

# 1) inspecionar versões de um dataset público do Roboflow Universe
python ml/train_incident_model.py inspect --workspace testingforyolo --project floods-by-agroudy

# 2) baixar em formato YOLOv8
python ml/train_incident_model.py download \
  --workspace testingforyolo --project floods-by-agroudy --version 2 --out ml/datasets/flood

# 3) coletar NEGATIVOS: frames das câmeras CET em tempo seco / noite / chuva-sem-alagar.
#    Rode em horários variados ao longo de alguns dias e revise a pasta depois,
#    apagando qualquer frame que tenha água acumulada de verdade.
python ml/collect_negatives.py --hours 12                    # sem --hours: roda até Ctrl+C
python ml/collect_negatives.py --cameras 22,23,180 --interval 30

# 4) fundir num dataset de 1 classe (--flood é repetível; '*' = todas as classes viram alagamento)
python ml/train_incident_model.py merge \
  --flood ml/datasets/flood --flood-classes "*" \
  --negatives ml/datasets/negativos_cet \
  --out ml/datasets/incidentes --limpar

# 5) treinar (GPU CUDA por padrão; base yolo11s, early stopping em 30 épocas)
python ml/train_incident_model.py train --data ml/datasets/incidentes/data.yaml --epochs 120
```

O `best.pt` é copiado para `ml/models/gx-incident.pt` e o peso anterior vira
`gx-incident-anterior.pt`. Reinicie o backend para carregar.

**Antes de confiar no peso novo:** rode o detector num punhado de frames CET reais e
confirme que a caixa fantasma sumiu. Se ainda houver, suba `GX_YOLO_INCIDENT_CONF`
(0,45 → ~0,6 → mais).
