# Testes, segurança e limitações

[← voltar ao README](../README.md#documentação)

## 17. Testes

```bash
# Backend — SQLite em memória
cd backend
venv\Scripts\python -m pytest tests -q

# Frontend — testes do módulo puro de formatação
npm run test:frontend

# Data Fusion isolado
python -m data_fusion.test_fusion
python -m data_fusion.test_historico_alagamento
```

### Distribuição da suíte de backend

| Arquivo | Cobre |
|---|---|
| `test_live_detection.py` | Gatilho de três faixas, veto/corroboração TomTom, cooldowns, dedup |
| `test_websocket.py` | Protocolo, broadcast, conexões mortas, ping/pong |
| `test_flood_detection.py` | Loop de alagamento, contexto climático, prior histórico |
| `test_deteccao.py` | Status e testador YOLO, limites de upload, rotas de escrita ausentes |
| `test_localizacoes.py` | Consulta, filtro por região e escrita bloqueada (405) |
| `test_dados_contextuais.py` | Consulta, filtros e escrita bloqueada (405) |
| `test_eventos.py` · `test_evidencias.py` · `test_regioes.py` · `test_fontes.py` | Consulta e filtros |
| `test_cet_camera_catalog.py` | Distância, câmera mais próxima, frame desatualizado |
| `test_data_fusion_service.py` | Promoção, rebaixamento, arredondamento do limiar, log só na mudança, migração de categoria |
| `test_detector_concorrencia.py` | Trava de carga, semáforo e lock por modelo; config do YOLO via `Settings` |
| `test_e2e.py` | Fluxos ponta a ponta |
| `test_inmet_alert_source.py` | Parsing de aviso |
| `test_broadcast.py` · `test_logs.py` | Agendamento entre threads; consulta de logs |
| `test_event_retention.py` | Purga, colapso, propagação de remoção |
| `test_tomtom_traffic_source.py` | Índice, indisponibilidade, via fechada |

### Convenções da suíte

- `conftest.py` força `settings.gx_monitoramento_ativo = False` — nenhuma thread de rede real
  sobe durante os testes, por mais que o `.env` local esteja ligado
- SQLite em memória com `StaticPool` e `PRAGMA foreign_keys=ON`
- **Não existem rotas de criação de evento**, então as fixtures (`criar_evento`,
  `criar_evidencia`) montam os dados direto no banco — que é como o sistema real os produz
  (`detection_events.py` grava pelo mesmo caminho)

---

## 18. Segurança e limitações

### Sem autenticação — e por quê

O sistema **não tem login, cadastro, perfis nem sessão**. Qualquer cliente que alcance a API
consulta os dados e chama as rotas. Isso é intencional: os eventos nascem de detecção
automática em câmera, não de um operador humano que precise ser identificado, e o painel é
de leitura.

A consequência é que **a proteção é de rede, não de aplicação**. Rode em rede local ou atrás
de um proxy reverso que faça o controle de acesso. `CORS_ORIGINS` restringe apenas quais
origens de navegador podem chamar a API e **não substitui isso**.

O WebSocket `/ws` abre na conexão e anuncia `{"tipo":"pronto"}` — não há
handshake de credencial.

Se a operação um dia exigir identificar quem agiu, a camada removida está no histórico:
`database/migrations/001_security.sql` (tabelas `usuarios` e `auditoria_acoes`) e o commit
que aplicou `003_remove_auth.sql`.

### Riscos conhecidos

- Quem alcança a porta da API tem acesso total, inclusive às rotas de escrita. **Não exponha
  à internet aberta** sem uma camada de acesso na frente.
- Não há trilha por usuário. O registro que sobra é de sistema, em `logs_sistema`.
- Em produção: HTTPS, CORS restritivo, TLS no banco, gerenciador de segredos.

### Limitações técnicas assumidas

- **YOLO COCO não é detector de incidente.** Ele reconhece objetos. Congestionamento é
  inferido por contagem + corroboração externa; alagamento exige o peso próprio.
- **O peso de alagamento ainda produz falso positivo.** Por isso `GX_YOLO_INCIDENT_CONF`
  está em 0,6 (mais alto que o de veículos) e o prior histórico derruba a confiabilidade de
  detecção sem chuva em via que nunca alagou.
- **Coordenadas são aproximadas** — câmeras e pontos de alagamento estão em nível de
  cruzamento, não do poste.
- **Latência e FPS dependem do hardware.** CPU tem latência maior; GPU exige CUDA/Ultralytics
  compatíveis. Meça com `backend/benchmark_latencia.py` (frames reais da CET), não por
  estimativa.
- **Privacidade:** só imagens de câmeras públicas da CET são gravadas, e apenas quando viram
  evidência de um evento; o testador YOLO do painel apaga o upload logo após a inferência.
- **Fontes públicas não substituem validação operacional humana.**

### Pendências

- Decidir se `frontend/dist/` deve continuar versionado
- Em produção MySQL: aplicar todas as migrações de `database/migrations/`, inclusive as
  destrutivas `003`, `004`, `005` e `006`
