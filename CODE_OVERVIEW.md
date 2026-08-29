# GX — Visão geral técnica

## Fluxo operacional

```text
Operador / fontes públicas / câmera autorizada
                │
                ▼
     Frontend TypeScript (Leaflet + painel GX)
                │ REST, WebSocket, SSE
                ▼
       FastAPI + SQLAlchemy + SQLite/MySQL
          ├─ Eventos, alertas, evidências e regiões
          ├─ Data Fusion (confiabilidade)
          ├─ Open-Meteo: clima e qualidade do ar
          └─ YOLO: upload de imagem / quadro capturado
```

## Componentes principais

| Área | Arquivos | Estado |
|---|---|---|
| Painel operacional | `frontend/index.html`, `frontend/src/app.ts`, `frontend/css/style.css` | Operacional; mapa Leaflet escuro, alertas e feed compactos. |
| Atualização em tempo real | `backend/app/routers/websocket.py`, `tempo_real.py`, `broadcast.py` | WebSocket com SSE e polling como fallback. |
| Dados públicos | `backend/app/services/weather_source.py`, `routers/fontes.py` | Clima e AQI/PM2.5 do Open-Meteo. |
| Visão computacional | `ml/detector.py`, `routers/deteccao.py` | YOLO11n local para veículos; câmera captura quadro sob autorização. |
| Confiabilidade | `data_fusion/`, `routers/fusion.py` | Score de fontes e evidências por evento. |

## Tecnologias e referências

| Tecnologia | Uso no GX | Referência oficial |
|---|---|---|
| FastAPI | API REST, uploads e endpoints operacionais | https://fastapi.tiangolo.com/ |
| Uvicorn | Servidor ASGI local | https://www.uvicorn.org/ |
| SQLAlchemy | Persistência e modelos relacionais | https://docs.sqlalchemy.org/ |
| Pydantic Settings | Configuração e validação de ambiente | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ |
| Leaflet + CARTO Dark | Mapa operacional aberto | https://leafletjs.com/ e https://carto.com/attributions/ |
| Open-Meteo | Clima, AQI e PM2.5 ao vivo | https://open-meteo.com/en/docs e https://open-meteo.com/en/docs/air-quality-api |
| Ultralytics YOLO11n | Inferência local de veículos/trânsito | https://docs.ultralytics.com/ |
| WebRTC `getUserMedia` | Câmera autorizada no navegador | https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia |
| TypeScript | Frontend e contratos de interface | https://www.typescriptlang.org/docs/ |
| Pytest | Testes automatizados | https://docs.pytest.org/ |

## Estado de execução validado (25/08/2026)

- Frontend local: `http://127.0.0.1:5500/` responde com HTTP 200.
- Backend local: `GET /health` retorna `{"status":"ok"}`.
- YOLO: dependências Ultralytics/Pillow e o peso local `ml/models/yolo11m.pt` estão instalados; o painel apresenta o motor como disponível.
- Inferência real: detecções COCO de veículos são registradas como `observacao_visual`, sem promover automaticamente a detecção a congestionamento ou incidente.
- Qualidade: `132 passed` na suíte `backend/tests` e `7 passed` na suíte do frontend.

## Limites atuais

- YOLO11n é um modelo COCO: detecta veículos e o GX os registra como `observacao_visual` até existir confirmação por uma fonte independente.
- Classes urbanas como alagamento e buraco exigem pesos próprios apontados por `GX_YOLO_MODEL`.
- Vídeo contínuo depende de uma câmera autorizada; o fluxo atual captura quadros pelo navegador para preservar consentimento e controlar custo de inferência.
- Fontes públicas não substituem validação operacional humana.

## Como validar localmente

```powershell
npm.cmd run build:frontend
cd backend
venv\Scripts\python -m pytest tests -q
Invoke-RestMethod http://127.0.0.1:8000/deteccao/status
```
