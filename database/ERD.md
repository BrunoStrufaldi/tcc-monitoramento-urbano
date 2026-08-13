# Diagrama entidade-relacionamento

```mermaid
erDiagram
    regioes ||--o{ localizacoes : contem
    regioes ||--o{ eventos : referencia
    regioes ||--o{ dados_contextuais : contextualiza
    fontes_dados ||--o{ eventos : origina
    fontes_dados ||--o{ evidencias_visuais : captura
    fontes_dados ||--o{ dados_contextuais : fornece
    localizacoes ||--o{ eventos : localiza
    eventos ||--o{ evidencias_visuais : comprova
    eventos ||--o{ dados_contextuais : enriquece
    eventos ||--o{ notificacoes : dispara
    eventos ||--o{ logs_sistema : referencia
```

| Tabela | Função |
|--------|--------|
| `regioes` | Divisão geográfica da cidade |
| `localizacoes` | Coordenadas e endereço normalizados |
| `fontes_dados` | Sensores, APIs, YOLO, fusão, manual |
| `eventos` | Ocorrência urbana |
| `evidencias_visuais` | Imagens/vídeos e detecções YOLO |
| `dados_contextuais` | Clima, trânsito e dados auxiliares |
| `notificacoes` | Alertas enviados por canal |
| `logs_sistema` | Auditoria e diagnóstico |
