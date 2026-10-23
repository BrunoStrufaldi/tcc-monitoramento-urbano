# syntax=docker/dockerfile:1
#
# Imagem do MotSP para o Cloud Run: API, painel e YOLO rodando em CPU.

# ---------- Etapa 1: compila o TypeScript do painel ----------
FROM node:20-slim AS frontend
WORKDIR /build
COPY package.json package-lock.json ./
RUN npm install --no-audit --no-fund
COPY frontend ./frontend
RUN npx tsc -p frontend/tsconfig.json

# ---------- Etapa 2: execução ----------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    # Sem isso os acentos saem errados nos logs.
    LANG=C.UTF-8 \
    PYTHONIOENCODING=utf-8 \
    # No Cloud Run só dá para gravar arquivos em /tmp.
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    MPLCONFIGDIR=/tmp/matplotlib \
    # Limita as threads do torch aos 2 processadores do container.
    OMP_NUM_THREADS=2 \
    # O TTA deixa a detecção duas vezes mais lenta, então fica desligado em CPU.
    GX_YOLO_TTA=false

# Bibliotecas do sistema que o opencv precisa.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Versão do torch só para CPU, bem menor que a padrão, que vem com CUDA.
RUN pip install --no-cache-dir torch==2.5.1 torchvision==0.20.1 \
        --index-url https://download.pytorch.org/whl/cpu

# O requirements-yolo.txt não entra aqui porque só serve para treinar.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && pip install --no-cache-dir "ultralytics>=8.3.0"

# Mantém a estrutura de pastas do projeto, porque o código importa ml e
# data_fusion a partir da raiz.
COPY backend ./backend
COPY ml ./ml
COPY data_fusion ./data_fusion
COPY database ./database
# O próprio FastAPI serve o painel.
COPY --from=frontend /build/frontend ./frontend

# O Cloud Run informa a porta em $PORT. O uvicorn sobe a partir de backend/,
# igual ao start.ps1.
ENV PORT=8080
EXPOSE 8080
WORKDIR /app/backend
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
