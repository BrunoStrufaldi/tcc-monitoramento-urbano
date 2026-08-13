# Módulo YOLO (visão computacional)

Espaço reservado para integração futura com detecção de objetos em vídeo/imagem.

## Planejamento

- `ml/models/` — pesos e configurações do YOLO
- `ml/pipelines/` — pré-processamento e inferência
- `ml/services/detector.py` — publica eventos via `POST /eventos`

Eventos gerados pelo YOLO devem usar `fonte_id` do tipo `yolo` em `fontes_dados`.
