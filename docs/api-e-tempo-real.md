# API HTTP e tempo real

[← voltar ao README](../README.md#documentação)

## 7. API HTTP

A documentação interativa fica em `http://localhost:8000/docs` (Swagger, gerado pelo FastAPI).

### Serviço

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | O painel. Com `GX_SERVE_FRONTEND=false`, mostra o status da API. |
| GET | `/api/status` | Status da API. |
| GET | `/health` | Verificação de saúde (`{"status":"ok"}`). |

### Eventos (somente leitura)

| Método | Rota | Parâmetros |
|---|---|---|
| GET | `/eventos` | `status`, `tipo`, `limite` (1 a 500, padrão 100), `janela_minutos` (0 = todos; padrão = `GX_EVENTO_JANELA_MINUTOS`) |
| GET | `/eventos/{id}` | nenhum |

Por padrão a lista só traz eventos detectados nos últimos 45 minutos. É um painel ao vivo,
e não um histórico.

### Data Fusion

| Método | Rota | Descrição |
|---|---|---|
| GET | `/fusion/eventos/{id}/confiabilidade` | Calcula sem gravar. |
| POST | `/fusion/eventos/{id}/recalcular` | Com `?persistir=true` (padrão), grava em `eventos.confianca`, ajusta o status e registra no log se ele mudar. |

A resposta traz `confiabilidade`, `nivel`, `limiar_ativo` e a lista de `componentes`, com
`pontuacao`, `peso`, `contribuicao` e um `detalhe` em texto. É isso que o painel mostra
para explicar a confiança do evento.

### Visão computacional

| Método | Rota | Descrição |
|---|---|---|
| GET | `/deteccao/classes` | Classes do sistema e um aviso sobre os limites do modelo padrão do YOLO. |
| GET | `/deteccao/status` | Se os dois modelos estão disponíveis, o caminho deles, o erro de carregamento e o `min_veiculos_transito`. |
| POST | `/deteccao/imagem` | Envia uma imagem e roda o modelo de veículos. PNG, JPG ou WEBP de até 10 MB; o arquivo temporário é apagado no fim. |
| POST | `/deteccao/incidente` | Envia uma imagem e roda o modelo de alagamento. É só um teste: não cria evento nem evidência. |

### Consulta de apoio

| Método | Rota | Descrição |
|---|---|---|
| GET | `/evidencias` | Filtros: `evento_id`, `tipo`, `limite`. |
| GET | `/evidencias/{id}` | nenhum |
| GET | `/evidencias/arquivo/{nome}` | Entrega a imagem local. Usa `Path(nome).name` para não deixar acessar outras pastas. |
| GET | `/logs` | Filtros: `nivel`, `modulo`, `evento_id`, `limite`. |
| GET | `/dados-contextuais` | Filtros: `evento_id`, `regiao_id`, `categoria`, `limite`. Só a coleta automática grava esses dados. |

### Cadastro (somente leitura)

| Rota | Métodos |
|---|---|
| `/regioes` | GET · GET/{id} |
| `/fontes` | GET · GET/{id} |
| `/localizacoes` | GET · GET/{id} |

O deploy não tem login, então nenhuma rota pública grava cadastros nem dados de contexto
(POST, PATCH e DELETE respondem 405). Quem grava é o próprio backend: a detecção cria o
evento, a localização e a evidência, e a coleta de clima, INMET e trânsito grava o
contexto.

### Fontes externas ao vivo (proxy)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/fontes/tempo-real/clima` | Open-Meteo: temperatura, precipitação, chuva, vento e código do tempo. |
| GET | `/fontes/tempo-real/ar` | Open-Meteo Air Quality: AQI americano e europeu, PM2.5 e PM10. |

As duas aceitam `latitude` e `longitude` (o padrão é o centro de São Paulo).

### Tempo real

| Protocolo | Rota | Descrição |
|---|---|---|
| WS | `/ws` | Canal dos eventos. |
| GET | `/events/stream` | SSE, usado se o WebSocket falhar. |
| GET | `/events/connected` | Quantos clientes SSE estão conectados. |

> Resumo: nenhuma rota cria, edita ou remove eventos ou evidências. Isso é feito pela
> detecção contínua. A única rota que grava alguma coisa é o recálculo do Data Fusion.

---

## 8. Tempo real: WebSocket, SSE e polling

### Protocolo do `/ws`

Não há etapa de autenticação: o servidor aceita a conexão e já manda `{"tipo": "pronto"}`.
Toda mensagem é um JSON com três campos:

```json
{
  "tipo": "evento_criado",
  "timestamp": "2026-09-04T12:00:00+00:00",
  "dados": { }
}
```

Do servidor para o cliente:

| `tipo` | `dados` | Enviado por |
|---|---|---|
| `pronto` | nenhum | Quando a conexão é aceita. |
| `evento_criado` | `EventoResponse` completo | `detection_events.registrar_deteccao` |
| `evento_atualizado` | `EventoResponse` completo | `detection_events.publicar_evento`, quando o evento é renovado no mesmo ponto ou quando o recálculo muda o status |
| `evento_removido` | `{"id": int}` | `event_retention.purgar_eventos_expirados` e `colapsar_eventos_duplicados` |
| `pong` | `{}` | Resposta ao `ping` |

Do cliente para o servidor: só `{"tipo":"ping"}`.

### Como o broadcast atravessa threads

As detecções rodam em threads comuns, fora do loop assíncrono do FastAPI. O
`app/broadcast.py` resolve isso: o `set_main_loop()` guarda o loop quando o sistema inicia
e o `schedule_coroutine()` usa `asyncio.run_coroutine_threadsafe` para agendar o envio.
Se o loop não estiver rodando, a chamada é ignorada sem erro. Isso acontece nos testes, e
é de propósito.

### Cascata de fallback (frontend)

```text
WebSocket ──falha──► SSE (/events/stream) ──falha──► Polling (15 s)
```

- Reconexão com espera crescente: 1 s → 2 s → 4 s → … → 128 s (no máximo 8 tentativas)
- Ping/pong a cada 30 s para a conexão não cair
- De tempos em tempos a lista completa é recarregada, mesmo com o canal funcionando, para
  nada ficar diferente da API
- O evento selecionado e os filtros continuam iguais durante as atualizações
- Conexões que caíram são removidas sozinhas no envio

| Estado | Selo | Cor |
|---|---|---|
| `ws` | "Sistema ao vivo" | verde |
| `sse` | "Sistema ao vivo" (o canal aparece só no `title`) | azul |
| `polling` | "Sistema em polling" | amarelo |
| `disconnected` | "Desconectado" | cinza |
