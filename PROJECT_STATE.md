# Estado do Projeto GX

**Última atualização**: ETAPA 16 — 2026-08-25

## Resumo

Sistema de Notificações Urbanas em Tempo Real para TCC. API FastAPI + frontend TypeScript + Leaflet escuro + Data Fusion + YOLO real para veículos. Atualização em tempo real via WebSocket com fallback SSE → Polling e fontes públicas de clima/qualidade do ar.

## Status das Etapas

| Etapa | Status | Detalhes |
|-------|--------|----------|
| ETAPA 0 — Proteger trabalho | Concluída | .gitignore corrigido, commit checkpoint |
| ETAPA 1 — Validar execução | Concluída | npm install, build TS, 82 testes passando |
| ETAPA 2 — Consistência de contratos | Concluída | Enums Literal[], removido "info" do frontend |
| ETAPA 3 — Finalizar frontend | Concluída | Mobile, ARIA, sr-only, touch targets |
| ETAPA 4 — Tempo real | Concluída | SSE + EventSource + reconexão exponencial |
| ETAPA 5 — Prova de conceito YOLO | Concluída | ml/detector.py simulado, 5 endpoints |
| ETAPA 6 — Teste ponta a ponta | Concluída | 5 fluxos E2E, 96/96 testes |
| ETAPA 7 — Documentação | Concluída | README, PROJECT_STATE, ml/README |
| ETAPA 8 — Validação final | Concluída | Build limpo, 96/96 testes, data fusion OK |
| ETAPA 9 — WebSocket em tempo real | Concluída | WS manager, endpoint /ws, fallback cascata, 115 testes |
| ETAPA 10 — CSS Premium | Concluída | Tokens semânticos, sólidos, 1849 linhas CSS |
| ETAPA 11 — Validação final frontend | Concluída | Auditado 9 resoluções, 4 zooms, acessibilidade, edge cases |
| ETAPA 12 — Operação ao vivo | Concluída | Leaflet/CARTO, Open-Meteo, SSE validado, câmera autorizada e YOLO11n real |
| ETAPA 13 — Validação operacional | Concluída | Build do frontend, API local, Open-Meteo e YOLO11n verificados; 122 testes automatizados passando. |
| ETAPA 14 — Verificação integrada local | Concluída | Frontend compilado, API e painel iniciados; 132 testes de backend e 7 testes de frontend passaram. Login, Bearer centralizado e autenticação do WebSocket principal validados automaticamente. |
| ETAPA 15 — Integridade operacional | Concluída | Registros demonstrativos removidos com backup; COCO gera observações, confirmação repete inferência no servidor, evidência original + imagem anotada e WebSocket real ativado. |
| ETAPA 16 — Atualização geral | Concluída | Documentação sincronizada em 25/08/2026; frontend recompilado; 132 testes de backend e 7 testes de frontend validados. |

## Números

- **132 testes** pytest (SQLite em memória)
- **7 testes** Node.js do frontend
- **8 models** SQLAlchemy (arquivo único por entidade)
- **11 routers** FastAPI (+ WebSocket)
- **YOLO11n real** para objetos COCO, normalizados como `observacao_visual`; incidentes urbanos aguardam pesos especializados e validação
- **4 severidades**: baixa, media, alta, critica
- **3 status evento**: ativo, em_analise, resolvido
- **WebSocket** com fallback cascata: WS → SSE → Polling
- **1849 linhas CSS** — design tokens premium, dark theme sólido

## Design Tokens Premium

### Brand
| Token | Valor | Uso |
|-------|-------|-----|
| `--gx` | `#FF5500` | Cor principal (botoes, badges) |
| `--gx-light` | `#FF8A00` | Acentos, hover, links |
| `--gx-dim` | `rgba(255,138,0,0.10)` | Backgrounds de acento |

### Superfícies Sólidas
| Token | Valor | Uso |
|-------|-------|-----|
| `--bg-base` | `#0C0C0C` | Fundo base |
| `--bg-panel` | `#111111` | Painéis |
| `--bg-raised` | `#161616` | Elementos elevados |
| `--bg-card` | `#1A1A1A` | Cards |
| `--bg-input` | `#0F0F0F` | Campos de entrada |
| `--bg-hover` | `#1E1E1E` | Hover state |
| `--bg-active` | `#222222` | Active state |

### Semânticos Operacionais
| Token | Cor | Uso |
|-------|-----|-----|
| `--ok` | `#2EAA5A` | Sucesso, ativo |
| `--warn` | `#E6A817` | Atenção, médio |
| `--danger` | `#DC3545` | Erro, crítico |
| `--info` | `#4A90D9` | Informação |

## Protocolo WebSocket

### Endpoint

```
ws://host:port/ws
```

### Formato das Mensagens

Todas as mensagens são JSON com 3 campos:

```json
{
  "tipo": "evento_criado",
  "timestamp": "2026-08-14T12:00:00+00:00",
  "dados": { ... }
}
```

### Mensagens Servidor → Cliente

| `tipo` | `dados` | Trigger |
|--------|---------|---------|
| `evento_criado` | EventoResponse completo | `POST /eventos` |
| `evento_atualizado` | EventoResponse completo | `PATCH /eventos/{id}` |
| `evento_removido` | `{"id": int}` | `DELETE /eventos/{id}` |
| `notificacao_criada` | NotificacaoResponse completo | `POST /notificacoes` |
| `notificacao_atualizada` | NotificacaoResponse completo | `PATCH /notificacoes/{id}`, `/lida`, `/arquivar` |
| `pong` | `{}` | Resposta a `ping` |

### Mensagens Cliente → Servidor

| `tipo` | `dados` | Resposta |
|--------|---------|----------|
| `ping` | `{}` | `pong` |

### Cascata de Fallback (Frontend)

```
WebSocket (ws) ──falha──► SSE (/events/stream) ──falha──► Polling (15s)
     ▲                          ▲                              │
     │ Reconexão exponencial    │ Reconexão exponencial        │ Contínuo
     │ max 8 tentativas         │                              │
```

### Estados de Conexão

| Estado | Badge | Cor | Significado |
|--------|-------|-----|-------------|
| `ws` | "Tempo real" | Verde | WebSocket conectado |
| `sse` | "Tempo real (SSE)" | Azul | Fallback SSE ativo |
| `polling` | "Polling" | Amarelo | Polling a cada 15s |
| `disconnected` | "Desconectado" | Cinza | Tentando reconectar |

### Garantias

- Seleção e filtros preservados durante atualizações
- Reconnection exponencial: 1s → 2s → 4s → 8s → ... → 128s (max 8)
- Ping/pong a cada 30s para manter conexão viva
- Conexões mortas removidas automaticamente no broadcast
- SSE e polling funcionam como fallback completo

## Validação Frontend (Etapa 11)

### Resoluções Testadas

| Categoria | Resolução | Breakpoint CSS |
|-----------|-----------|----------------|
| Desktop | 1920×1080 | Nenhum (full 3-col) |
| Desktop | 1440×900 | Nenhum (full 3-col) |
| Desktop | 1366×768 | Nenhum (full 3-col) |
| Tablet | 1024×768 | max-width:1200px (right panel → drawer) |
| Tablet | 768×1024 | max-width:980px (sidebar hidden, map full) |
| Mobile | 430×932 | max-width:680px (mobile layout) |
| Mobile | 390×844 | max-width:680px |
| Mobile | 375×667 | max-width:680px |
| Mobile | 320×568 | max-width:680px + 480px (1-col KPIs) |

### Zoom Testado

| Zoom | Efeito |
|------|--------|
| 80% | Mais espaço, todos os painéis visíveis |
| 100% | Padrão |
| 125% | Breakpoints ativados mais cedo |
| 150% | Sidebar oculta, layout compacto |

### Acessibilidade

- `prefers-reduced-motion: reduce` — todas as animações desabilitadas
- `:focus-visible` — outline laranja em todos os controles interativos
- `tabindex="0"` + `role="button"` em todos os event cards
- Navegação por teclado (Enter/Space) nos event cards
- `aria-label` em botões e seções
- Skip link "Pular para lista de eventos"
- Cores com contraste suficiente em fundo escuro

### Edge Cases Validados

- **Lista vazia**: "Nenhum evento encontrado." com borda tracejada
- **Evento sem confiança**: Badge oculto, barra não renderizada
- **Evento sem fonte**: Footer oculto
- **Evento sem evidência**: "Nenhuma evidência visual para este evento"
- **Títulos longos**: `line-clamp: 2` + `text-overflow: ellipsis`
- **API indisponível**: Status "API indisponível" + mensagem de erro com URL
- **WebSocket desconectado**: Badge "Desconectado", fallback automático

### Correções Aplicadas na Validação

1. **CSS**: `--color-muted` → `--text-muted` (HTML severity badge)
2. **CSS**: `--color-neon` → `--gx-light` (HTML fusão badge)
3. **TS**: `--color-text-secondary` → `--text-secondary` (renderSeverityFilters)
4. **TS**: `--color-muted` → `--text-muted` (renderActivityFeed, renderSelectedEvent)
5. **CSS**: `.event-title` adicionado `overflow: hidden` + `-webkit-line-clamp: 2`
6. **CSS**: `.kpi-value` adicionado `overflow: hidden` + `text-overflow: ellipsis`
7. **CSS**: `.control:focus` → `.control:focus-visible` (foco apenas por teclado)
8. **TS**: Event cards com `tabindex="0"`, `role="button"`, handler keydown

## Arquivos Chave

- `frontend/src/app.ts` — Lógica principal do frontend (~1492 linhas)
- `frontend/css/style.css` — Design tokens premium, dark theme (~1849 linhas)
- `frontend/index.html` — HTML com ARIA, skip link (~389 linhas)
- `frontend/dist/app.js` — Build output gerado por tsc
- `backend/app/main.py` — FastAPI app com 11 routers
- `backend/app/ws_manager.py` — ConnectionManager para WebSocket
- `backend/app/routers/websocket.py` — Endpoint /ws
- `backend/app/schemas/evento.py` — Schemas com Literal validation
- `data_fusion/fusion.py` — Motor de confiabilidade
- `ml/detector.py` — Integração YOLO11n local para inferência de imagens
- `database/schema.sql` — DDL 8 tabelas
- `backend/tests/` — 132 testes

## Pendências Conhecidas

- **Sessão:** o token é mantido apenas em `sessionStorage`; ainda não há refresh token nem encerramento explícito de sessão.
- **Produção:** configurar MySQL, aplicar `database/migrations/001_security.sql`, restringir CORS/HTTPS e usar um gerenciador de segredos.
- **Higiene de build:** decidir se `frontend/dist/` deve ser versionado. As dependências não utilizadas `http` e `httpx2` foram removidas dos manifestos.
