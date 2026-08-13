# Sistema de Notificações Urbanas em Tempo Real 

Protótipo com API FastAPI, MySQL, frontend com Google Maps, Data Fusion e estrutura para YOLO.

## Estrutura

```
Projeto Gx/
├── backend/           # API FastAPI
├── database/          # schema.sql + ERD
├── frontend/          # Mapa + lista de eventos
├── data_fusion/       # Confiabilidade (IA + clima + fonte)
└── ml/                # Futuro: YOLO
```

## Pré-requisitos

- Python 3.11+
- MySQL 8.x
- Chave [Google Maps JavaScript API](https://console.cloud.google.com/)

## 1. Banco MySQL

```bash
mysql -u root -p < database/schema.sql
```

## 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env`:

```
DATABASE_URL=mysql+pymysql://usuario:senha@localhost:3306/notificacoes_urbanas
```

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Raiz: http://localhost:8000/ → `{"status":"online","message":"API do TCC rodando com sucesso"}`
- Docs: http://localhost:8000/docs

### Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Status da API |
| GET | `/health` | Health check |
| GET | `/eventos` | Lista eventos |
| POST | `/eventos` | Cria evento |
| GET | `/fusion/eventos/{id}/confiabilidade` | Score Data Fusion |
| POST | `/fusion/eventos/{id}/recalcular` | Recalcula e grava confiança |

## 3. Frontend

1. Copie `frontend/js/config.example.js` para `frontend/js/config.js` e preencha com a sua chave em `GOOGLE_MAPS_API_KEY`.
2. Sirva a pasta:

```bash
cd frontend
python -m http.server 5500
```

3. Abra http://localhost:5500

Marcadores por criticidade: baixa (verde), média (amarelo), alta (vermelho), crítica (roxo).

## 4. Data Fusion

```bash
python -m data_fusion.test_fusion
curl http://localhost:8000/fusion/eventos/2/confiabilidade
```

Pesos: IA 40%, clima 30%, fonte oficial 30%.

## Licença

Projeto acadêmico — TCC.
