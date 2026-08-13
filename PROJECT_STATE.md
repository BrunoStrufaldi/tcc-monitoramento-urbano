# Estado do Projeto GX

**Última atualização**: ETAPA 7 — 2026-08-13

## Resumo

Sistema de Notificações Urbanas em Tempo Real para TCC. API FastAPI + frontend TypeScript + Google Maps + Data Fusion + YOLO simulado.

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
| ETAPA 8 — Validação final | Pendente | Build final, testes, relatório |

## Números

- **96 testes** pytest (SQLite em memória)
- **8 models** SQLAlchemy (arquivo único por entidade)
- **10 routers** FastAPI
- **8 classes** YOLO urbanas (simuladas)
- **4 severidades**: baixa, media, alta, critica
- **3 status evento**: ativo, em_analise, resolvido
- **SSE** com reconexão exponencial (max 5 tentativas)

## Arquivos Chave

- `frontend/src/app.ts` — Lógica principal do frontend
- `backend/app/main.py` — FastAPI app com 11 routers
- `backend/app/schemas/evento.py` — Schemas com Literal validation
- `data_fusion/fusion.py` — Motor de confiabilidade
- `ml/detector.py` — Detector YOLO simulado
- `database/schema.sql` — DDL 8 tabelas
- `backend/tests/` — 96 testes

## Pendências Conhecidas

- `frontend/dist/` versionado (compilado) — decidir se deve ser gitignored
- `PROJECT_STATE.md` deletado no checkpoint, recriado nesta etapa
- `package.json` tinha dependência `http` (removida implicitamente)
- Não há MySQL configurado — testes usam SQLite em memória
