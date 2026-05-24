# Sistema de Notificações Urbanas em Tempo Real (TCC)

Monitoramento urbano com API FastAPI, MySQL, mapa interativo e módulo de Data Fusion.

## Estrutura

```
Projeto Gx/
├── backend/           # API FastAPI + SQLAlchemy
├── database/          # schema.sql (banco principal)
├── frontend/          # Mapa Google Maps
├── data_fusion/       # Cálculo de confiabilidade
├── ml/                # Reservado: YOLO (fase final)
└── PROJECT_STATE.md   # Estado e roadmap do TCC
```

## Pré-requisitos

- Python 3.11+
- MySQL 8.x
- Chave [Google Maps JavaScript API](https://console.cloud.google.com/) (frontend)

---

## 1. Ambiente virtual e dependências

```bash
cd backend
python -m venv venv
```

**Windows (ativar venv):**

```bash
venv\Scripts\activate
```

**Linux/macOS:**

```bash
source venv/bin/activate
```

**Instalar dependências:**

```bash
pip install -r requirements.txt
```

Pacotes principais: `fastapi`, `uvicorn`, `sqlalchemy`, `pymysql`, `python-dotenv`, `pydantic-settings`.

---

## 2. Configurar `.env`

Copie o exemplo e edite com sua senha MySQL:

```bash
copy .env.example .env
```

Conteúdo de `.env`:

```
DATABASE_URL=mysql+pymysql://root:SENHA@localhost/tcc_monitoramento_urbano
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5500,http://127.0.0.1:5500
```

---

## 3. Criar banco MySQL

```bash
mysql -u root -p < database/schema.sql
```

Isso cria o banco `tcc_monitoramento_urbano`, a tabela `eventos` e 3 registros de exemplo.

---

## 4. Rodar a API

Com o venv ativo, na pasta `backend`:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Raiz: [http://127.0.0.1:8000/](http://127.0.0.1:8000/) → `{"status":"online","message":"API do TCC rodando com sucesso"}`
- Swagger: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## 5. Endpoints de eventos (CRUD)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/eventos` | Lista (filtros: `status`, `tipo`, `criticidade`, `limite`) |
| GET | `/eventos/{id}` | Detalhe |
| POST | `/eventos` | Criar |
| PUT | `/eventos/{id}` | Atualizar |
| DELETE | `/eventos/{id}` | Excluir |

**Exemplo POST:**

```json
{
  "tipo": "transito",
  "descricao": "Congestionamento na marginal",
  "criticidade": "media",
  "latitude": -23.55,
  "longitude": -46.63,
  "status": "ativo",
  "confiabilidade": 0.7,
  "fonte": "api"
}
```

### Data Fusion (mantido)

| Método | Rota |
|--------|------|
| GET | `/fusion/eventos/{id}/confiabilidade` |
| POST | `/fusion/eventos/{id}/recalcular?persistir=true` |

---

## 6. Frontend (mapa)

```bash
cd frontend
python -m http.server 5500
```

Configure `frontend/js/config.js` com a chave do Google Maps e `API_BASE_URL=http://127.0.0.1:8000`.

Abra: [http://localhost:5500](http://localhost:5500)

---

## Roadmap

Consulte `PROJECT_STATE.md` para arquitetura completa e fases.

**YOLO não está implementado** — será a última fase, como módulo de automação visual em `ml/`.

## Licença

Projeto acadêmico — TCC.
