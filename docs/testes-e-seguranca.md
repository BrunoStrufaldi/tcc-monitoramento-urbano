# Testes, segurança e limitações

[← voltar ao README](../README.md#documentação)

## 17. Testes

```bash
# Backend (SQLite em memória)
cd backend
venv\Scripts\python -m pytest tests -q

# Frontend (testes do módulo de formatação)
npm run test:frontend

# Data Fusion sozinho
python -m data_fusion.test_fusion
python -m data_fusion.test_historico_alagamento
```

### Distribuição da suíte de backend

| Arquivo | O que testa |
|---|---|
| `test_live_detection.py` | Gatilho de três faixas, recusa e confirmação da TomTom, tempos de espera e câmera travada |
| `test_flood_detection.py` | Loop de alagamento, dados de clima, aviso do INMET e histórico da via |
| `test_data_fusion_service.py` | Promoção, rebaixamento, arredondamento do limite, log só quando o status muda e troca de categoria |
| `test_consultas.py` | Consulta e filtros de todas as rotas, 404 e escrita bloqueada (405) |
| `test_evidencias.py` | Evidência gravada pela detecção (imagem original e hash) e download do arquivo |
| `test_tempo_real.py` | WebSocket, SSE, conexões que caíram, ping/pong e envio entre threads |
| `test_deteccao.py` | Status e testador do YOLO, upload inválido e modelo indisponível |
| `test_detector_concorrencia.py` | Trava de carregamento, limite de detecções e trava por modelo; configuração do YOLO pelo `Settings` |
| `test_event_retention.py` | Limpeza, junção de repetidos e aviso de remoção |
| `test_e2e.py` | Fluxos de ponta a ponta, status da API e cache do painel |
| `test_cet_camera_catalog.py` | Câmera mais próxima e imagem travada |
| `test_inmet_alert_source.py` · `test_tomtom_traffic_source.py` | Leitura das APIs externas e falha de rede |

### Convenções da suíte

- O `conftest.py` força `settings.gx_monitoramento_ativo = False`, então nenhuma thread
  acessa a rede durante os testes, mesmo que o `.env` local esteja com o monitoramento
  ligado
- SQLite em memória com `StaticPool` e `PRAGMA foreign_keys=ON`
- Não existem rotas de criação de evento, então as funções de apoio (`criar_evento`,
  `criar_evidencia`) gravam os dados direto no banco, do mesmo jeito que o sistema real
  faz (o `detection_events.py` grava pelo mesmo caminho)

---

## 18. Segurança e limitações

### Sem autenticação, e por quê

O sistema não tem login, cadastro, perfis nem sessão. Qualquer cliente que acesse a API
consegue consultar os dados e chamar as rotas. Isso é de propósito: os eventos vêm da
detecção automática nas câmeras, e não de um operador que precise ser identificado, e o
painel só consulta.

Por isso a proteção tem que ser feita na rede, e não na aplicação. Rode numa rede local ou
atrás de um proxy reverso que controle o acesso. O `CORS_ORIGINS` só limita quais sites
podem chamar a API pelo navegador e não substitui esse controle.

O WebSocket `/ws` abre assim que a conexão é feita e manda `{"tipo":"pronto"}`, sem pedir
credenciais.

Se um dia for preciso identificar quem fez cada ação, o código removido está no
histórico: `database/migrations/001_security.sql` (tabelas `usuarios` e
`auditoria_acoes`) e o commit que aplicou o `003_remove_auth.sql`.

### Riscos conhecidos

- Quem acessa a porta da API pode usar todas as rotas, inclusive o recálculo do Data
  Fusion. Não deixe a API aberta na internet sem um controle de acesso na frente.
- Não há registro por usuário. O único registro é o do sistema, em `logs_sistema`.
- Em produção: HTTPS, CORS restrito, TLS no banco e um gerenciador de segredos.

### Limitações técnicas assumidas

- O YOLO padrão não detecta incidentes, só objetos. O congestionamento é calculado pela
  contagem com a confirmação de outras fontes, e o alagamento precisa do modelo próprio.
- O modelo de alagamento ainda erra às vezes. Por isso o `GX_YOLO_INCIDENT_CONF` fica em
  0,6 (mais alto que o de veículos), e o histórico da via derruba a confiabilidade de uma
  detecção sem chuva numa via que nunca alagou.
- As coordenadas são aproximadas: câmeras e pontos de alagamento estão no nível do
  cruzamento, e não do poste.
- O tempo de resposta depende do hardware. Em CPU é mais lento, e a GPU precisa de versões
  compatíveis de CUDA e Ultralytics. Para medir, use o `backend/benchmark_latencia.py`
  (com imagens reais da CET).
- Privacidade: só são gravadas imagens de câmeras públicas da CET, e só quando viram
  evidência de um evento. O testador do YOLO no painel apaga a imagem enviada logo depois
  da detecção.
- As fontes públicas não substituem a validação feita por uma pessoa.

### Pendências

- Decidir se o `frontend/dist/` deve continuar no Git
- Em produção com MySQL: aplicar todas as migrações de `database/migrations/`, inclusive
  as destrutivas `003`, `004`, `005` e `006`
