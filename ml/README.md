# Módulo YOLO (visão computacional)

Espaço reservado para integração futura com detecção de objetos em vídeo/imagem.

## Planejamento sugerido

- `ml/models/` — pesos e configurações do YOLO
- `ml/pipelines/` — pré-processamento e inferência
- `ml/services/detector.py` — serviço que publica eventos na API (`POST /eventos`)

## Integração com a API

Eventos gerados pelo YOLO devem usar `fonte_id` correspondente à fonte `yolo` na tabela `fontes_dados`.
