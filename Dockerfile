# syntax=docker/dockerfile:1
#
# Imagem única do MotSP: API FastAPI + painel estático + inferência YOLO em CPU.
# Feita para o Cloud Run, que escala a zero — o container só existe enquanto
# alguém está usando o sistema.

# ---------- Etapa 1: compila o TypeScript do painel ----------
FROM node:20-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund
COPY frontend ./frontend
RUN npx tsc -p frontend/tsconfig.json

# ---------- Etapa 2: runtime ----------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Sem locale a imagem slim loga em ASCII e "Câmera" vira "C?mera" no
    # Cloud Logging.
    LANG=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    # Ultralytics e matplotlib querem escrever config em $HOME; no Cloud Run o
    # sistema de arquivos é read-only fora de /tmp.
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib \
    # O container roda com 2 vCPU. Sem isso o torch abre uma thread por core do
    # host e as inferências das câmeras brigam entre si.
    OMP_NUM_THREADS=2 \
    # Faz o próprio FastAPI servir o painel (ver app/main.py).
    GX_SERVE_FRONTEND=true

# libGL/libglib: dependências nativas do opencv, que vem junto com o ultralytics.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# torch de CPU explicitamente: o wheel padrão do PyPI arrasta ~2,5 GB de CUDA
# que não serve para nada no Cloud Run, que não tem GPU.
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 \
        --index-url https://download.pytorch.org/whl/cpu

# requirements-yolo.txt não é usado aqui: ele inclui o roboflow, que só a
# máquina que TREINA o modelo precisa.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && pip install --no-cache-dir "ultralytics>=8.3.0"

# O layout do projeto é preservado: app/routers/deteccao.py e
# app/services/data_fusion_service.py colocam a raiz no sys.path para importar
# `ml` e `data_fusion`, e ml/detector.py procura os pesos em ml/models/.
COPY backend ./backend
COPY ml ./ml
COPY data_fusion ./data_fusion
COPY database ./database
COPY --from=frontend /build/frontend ./frontend

# Painel e API na mesma origem: o config de produção resolve a URL da API pelo
# window.location, então o mesmo build funciona em qualquer domínio.
COPY frontend/js/config.prod.js ./frontend/js/config.js

# O Cloud Run injeta $PORT (8080). O uvicorn sobe a partir de backend/, igual
# ao start.ps1 local, para o sqlite e os caminhos relativos baterem.
ENV PORT=8080
EXPOSE 8080
WORKDIR /app/backend
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
