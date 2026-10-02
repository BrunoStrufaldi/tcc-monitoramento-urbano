# API HTTP e tempo real

[← voltar ao README](../README.md#documentação)

## 7. API HTTP

Documentação interativa em `http://localhost:8000/docs` (Swagger, gerado pelo FastAPI).

### Serviço

| Método | Rota | Descrição |
|---|---|---|
| GET | `/` | Status da API. |
| GET | `/health` | Health check (`{"status":"ok"}`). |

### Eventos — somente leitura

| Método | Rota | Parâmetros |
|---|---|---|
| GET | `/eventos` | `status`, `tipo`, `limite` (1–500, padrão 100), `janela_minutos` (0 = histórico completo; padrão = `GX_EVENTO_JANELA_MINUTOS`) |
| GET | `/eventos/{id}` | — |

Por padrão a listagem só retorna eventos detectados dentro da janela de 45 minutos: é um
quadro ao vivo, não um histórico.

### Data Fusion

| Método | Rota | Descrição |
|---|---|---|
| GET | `/fusion/eventos/{id}/confiabilidade` | Calcula sem gravar. |
| POST | `/fusion/eventos/{id}/recalcular` | `?persistir=true` (padrão) grava em `eventos.confianca`, ajusta o status e loga se ele mudar. |

A resposta traz `confiabilidade`, `nivel`, `limiar_ativo` e a lista de `componentes` com
`pontuacao`, `peso`, `contribuicao` e `detalhe` em texto — é isso que o painel exibe como
"por que este evento tem essa confiança".

### Visão computacional

| Método | Rota | Descrição |
|---|---|---|
| GET | `/deteccao/classes` | Classes urbanas mapeadas + aviso sobre limites do peso COCO. |
| GET | `/deteccao/status` | Disponibilidade dos **dois** modelos, caminho dos pesos, erro de carga e `min_veiculos_transito`. |
| POST | `/deteccao/imagem` | Upload → inferência com o modelo de objetos. PNG/JPG/WEBP até 10 MB; arquivo temporário apagado ao final. |
| POST | `/deteccao/incidente` | Upload → inferência com o modelo dedicado de alagamento. Isolado: não passa pelo pipeline de evento/evidência. |

### Consulta de apoio

| Método | Rota | Descrição |
|---|---|---|
| GET | `/evidencias` | Filtros: `evento_id`, `tipo`, `limite`. |
| GET | `/evidencias/{id}` | — |
| GET | `/evidencias/arquivo/{nome}` | Serve o JPEG local; usa `Path(nome).name` para bloquear travessia de diretório. |
| GET | `/logs` | Filtros: `nivel`, `modulo`, `evento_id`, `limite`. |
| GET | `/dados-contextuais` | Filtros: `evento_id`, `regiao_id`, `categoria`, `limite`. Gravado só pela coleta automática. |

### Cadastro — somente leitura

| Rota | Métodos |
|---|---|
| `/regioes` | GET · GET/{id} |
| `/fontes` | GET · GET/{id} |
| `/localizacoes` | GET · GET/{id} |

Não há login no deploy, então nenhuma rota pública escreve cadastro nem dado contextual
(POST/PATCH/DELETE respondem 405). Quem grava é o próprio backend: a detecção cria
evento/localização/evidência e a coleta de clima, INMET e trânsito grava o contexto.

### Fontes externas ao vivo (proxy)

| Método | Rota | Descrição |
|---|---|---|
| GET | `/fontes/tempo-real/clima` | Open-Meteo: temperatura, precipitação, chuva, vento, código do tempo. |
| GET | `/fontes/tempo-real/ar` | Open-Meteo Air Quality: AQI US/europeu, PM2.5, PM10. |

Ambas aceitam `latitude`/`longitude` (padrão: centro de São Paulo).

### Tempo real

| Protocolo | Rota | Descrição |
|---|---|---|
| WS | `/ws` | Canal operacional de eventos. |
| GET | `/events/stream` | SSE — fallback do WebSocket. |
| GET | `/events/connected` | Número de clientes SSE conectados. |

> **Resumo de escrita:** nenhuma rota cria, edita ou remove evento/evidência — isso é
> trabalho da detecção contínua. As rotas que ainda gravam são `/dados-contextuais`
> (ingestão de fonte), os CRUDs de cadastro `/regioes`, `/fontes`, `/localizacoes` e o
> recálculo da fusão.

---

## 8. Tempo real: WebSocket, SSE e polling

### Protocolo do `/ws`

Sem handshake: o servidor aceita a conexão e anuncia `{"tipo": "pronto"}` imediatamente.
Toda mensagem é JSON com três campos:

```json
{
  "tipo": "evento_criado",
  "timestamp": "2026-09-04T12:00:00+00:00",
  "dados": { }
}
```

**Servidor → Cliente**

| `tipo` | `dados` | Disparado por |
|---|---|---|
| `pronto` | — | Aceite da conexão. |
| `evento_criado` | `EventoResponse` completo | `detection_events.registrar_deteccao` |
| `evento_atualizado` | `EventoResponse` completo | `detection_events.publicar_evento` — refresco no mesmo ponto, recálculo da fusão que muda o status |
| `evento_removido` | `{"id": int}` | `event_retention.purgar_eventos_expirados` e `colapsar_eventos_duplicados` |
| `pong` | `{}` | Resposta a `ping` |

**Cliente → Servidor**: apenas `{"tipo":"ping"}`.

### Como o broadcast atravessa threads

As detecções rodam em threads síncronas, fora do event loop do FastAPI.
`app/broadcast.py` resolve isso: `set_main_loop()` guarda o loop no startup e
`schedule_coroutine()` usa `asyncio.run_coroutine_threadsafe` para agendar o envio.
Se o loop não estiver rodando, a chamada é ignorada silenciosamente (é o que acontece nos
testes, e é intencional).

### Cascata de fallback (frontend)

```text
WebSocket ──falha──► SSE (/events/stream) ──falha──► Polling (15 s)
```

- Reconexão exponencial: 1 s → 2 s → 4 s → … → 128 s (máx. 8 tentativas)
- Ping/pong a cada 30 s para manter a conexão viva
- Timer de ressincronização periódica: recarrega a lista completa mesmo com o canal vivo,
  para não acumular divergência
- Seleção do evento e filtros são preservados durante as atualizações
- Conexões mortas são removidas automaticamente no broadcast

| Estado | Badge | Cor |
|---|---|---|
| `ws` | "Sistema ao vivo" | verde |
| `sse` | "Sistema ao vivo" (canal só no `title`) | azul |
| `polling` | "Sistema em polling" | amarelo |
| `disconnected` | "Desconectado" | cinza |
