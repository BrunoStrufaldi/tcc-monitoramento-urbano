# Sistema de Notificações Urbanas em Tempo Real

Projeto TCC — API FastAPI, frontend TypeScript com Google Maps, Data Fusion, detecção YOLO (simulada) e SSE para atualizações em tempo real.

## Estrutura

```
Projeto Gx/
├── backend/                # API FastAPI (Python)
│   ├── app/
│   │   ├── models/         # 8 models SQLAlchemy
│   │   ├── routers/        # 10 routers (eventos, fusion, deteccao, tempo_real, etc.)
│   │   ├── schemas/        # Schemas Pydantic com Literal validation
│   │   └── services/       # Bridge data_fusion_service
│   └── tests/              # 96 testes (pytest + SQLite em memória)
├── frontend/
│   ├── src/app.ts          # TypeScript principal (navigation rail, event cards, filtros)
│   ├── dist/app.js         # Bundle compilado
│   ├── css/style.css       # UI premium dark (1456 linhas)
│   └── index.html          # SPA com ARIA labels, views, overlays
├── data_fusion/            # Motor de confiabilidade (IA 40%, clima 30%, fonte 30%)
├── ml/                     # Prova de conceito YOLO (simulado)
├── database/
│   ├── schema.sql          # DDL 8 tabelas + seed
│   └── ERD.md              # Diagrama entidade-relação
└── package.json            # Scripts: build:frontend, serve
```

## Pré-requisitos

- Python 3.11+
- Node.js 18+ (para build do frontend)
- MySQL 8.x (produção) ou SQLite (testes)
- Chave [Google Maps JavaScript API](https://console.cloud.google.com/)

## Início Rápido

### 1. Frontend (TypeScript)

```bash
npm install
npm run build:frontend    # Compila src/ → dist/
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` com suas credenciais MySQL (ou ignore para usar SQLite via testes).

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend (servir)

```bash
cd frontend
python -m http.server 5500
```

Abra http://localhost:5500

### 4. Testes

```bash
cd backend
pytest tests/ -v           # 96 testes
python -m data_fusion.test_fusion
```

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Status da API |
| GET | `/health` | Health check |
| **Eventos** | | |
| GET | `/eventos` | Lista eventos (filtros: status, tipo) |
| POST | `/eventos` | Cria evento |
| GET | `/eventos/{id}` | Obtém evento |
| PATCH | `/eventos/{id}` | Atualiza evento |
| DELETE | `/eventos/{id}` | Remove evento |
| **Data Fusion** | | |
| GET | `/fusion/eventos/{id}/confiabilidade` | Score de confiabilidade |
| POST | `/fusion/eventos/{id}/recalcular` | Recalcula e grava |
| **Tempo Real** | | |
| GET | `/events/stream` | SSE — eventos em tempo real |
| GET | `/events/connected` | Clientes SSE conectados |
| **YOLO (simulado)** | | |
| GET | `/deteccao/classes` | Classes detectáveis |
| POST | `/deteccao/simular` | Simula detecção |
| POST | `/deteccao/imagem` | Upload + detecção |
| POST | `/deteccao/video` | Detecção em frames |
| **Outros** | | |
| `/notificacoes` | CRUD notificações |
| `/regioes` | CRUD regiões |
| `/fontes` | CRUD fontes de dados |
| `/localizacoes` | CRUD localizações |
| `/evidencias` | CRUD evidências visuais |
| `/dados-contextuais` | CRUD dados contextuais |
| `/logs` | Logs do sistema |

## Arquitetura

- **Backend**: FastAPI + SQLAlchemy + Pydantic (Literal validation para enums)
- **Frontend**: TypeScript + Google Maps API + Navigation Rail + Event Cards premium
- **Data Fusion**: Motor de confiabilidade (IA 40%, clima 30%, fonte oficial 30%)
- **Tempo Real**: SSE (Server-Sent Events) com reconexão exponencial
- **YOLO**: Prova de conceito simulada (8 classes urbanas)
- **Testes**: 96 testes pytest com SQLite em memória

## Enums do Sistema

- **Severidade**: `baixa`, `media`, `alta`, `critica`
- **Status evento**: `ativo`, `em_analise`, `resolvido`
- **Canal notificação**: `painel`, `push`, `email`, `sms`, `webhook`
- **Status notificação**: `pendente`, `enviada`, `falha`, `lida`

## Licença

Projeto acadêmico — TCC.
