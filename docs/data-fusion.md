# Data Fusion e ciclo de vida do evento

[← voltar ao README](../README.md#documentação)

## 12. Data Fusion (confiabilidade)

Módulo `data_fusion/`, Python puro e sem dependência do FastAPI — pode ser testado isolado.

### As duas dimensões

| Dimensão | Peso | Fonte |
|---|---|---|
| **IA** | 4/7 ≈ 57% | `evidencias_visuais` — a melhor confiança YOLO do evento, mais o fato de haver modelo registrado |
| **Contexto** | 3/7 ≈ 43% | `dados_contextuais` com `categoria = contexto`: chuva (Open-Meteo), aviso INMET e histórico da via para alagamento; índice de veículos do frame e TomTom para trânsito |

Já foram três dimensões — IA 40%, clima 30% e **fonte oficial** 30% (pontuada pelo
`fontes_dados.tipo` do evento). Como todo evento nasce de uma fonte `yolo`, que já está
contada na IA, a fonte oficial pontuava sempre 0 e o rateio dava exatamente IA 57% /
contexto 43%. A dimensão saiu e os pesos passaram a ser esses 4:3 explícitos — os scores
continuaram idênticos (conferido em 620 cenários). O aviso do INMET, que é a fonte oficial
de verdade, entra como um dos sinais do contexto.

### Normalização de peso

Uma dimensão que pontua `0` significa "não utilizada", não "ruim". O peso dela vai para a
outra:

```python
peso_disponivel = soma dos pesos das dimensões com pontuação > 0
peso_efetivo(d) = PESO[d] / peso_disponivel
confiabilidade  = Σ pontuacao(d) × peso_efetivo(d)
```

Sem nenhum dado de contexto, a confiabilidade é a própria nota da IA.

### Peso do contexto conforme a concordância

Quando há **duas** fontes de contexto ao vivo (chuva + INMET, ou contagem de veículos +
TomTom), o peso-base do contexto é multiplicado por um fator entre **0,8×** (as fontes se
contradizem) e **1,4×** (dizem a mesma coisa), proporcional à concordância entre as notas
(divergência de 0,4 ou mais = contradição completa). Com uma fonte só, fica em 1,0×. O
histórico de alagamento não entra nessa conta: é prior estático, não testemunha do agora.

### Níveis

| Confiabilidade | Nível |
|---|---|
| ≥ 0,80 | `alta` |
| 0,55 – 0,79 | `media` |
| < 0,55 | `baixa` |

### Pontuação do contexto, por tipo de evento

As notas são rampas lineares entre âncoras (cada décimo do sinal mexe na nota), saturando
nas pontas.

**Alagamento** — combina até três insumos:

```text
chuva medida (Open-Meteo)               aviso INMET ativo (níveis categóricos)
  âncoras (mm/h → nota):                  grande perigo → 0,93
  0 → 0,30   5 → 0,55   15 → 0,78          perigo        → 0,80
  30 → 0,93  50 → 0,97                     perigo pot.   → 0,60
                                           sem aviso     → 0,40
        └──────────── média dos presentes ────────────┘
                          │
                          ▼
        ajuste pelo histórico da via (prior espacial)
          índice ≥ 7 → × 1,12   (ponto de alagamento crônico)
          índice ≥ 4 → × 1,06   (recorrente)
          índice > 0 → × 1,00   (histórico baixo)
          índice = 0 → × 0,90   (via sem histórico — leve cautela)
```

Chuva medida de **0,0 mm/h** conta como "sem sinal de chuva", não como leitura. Se não
houver chuva nem aviso ativo (só o visual do modelo), o histórico decide sozinho:

| Situação | Pontuação | Leitura |
|---|---|---|
| Histórico ausente da chave | 0,45 | genérico |
| Via com histórico ≥ 4 | 0,45 | "costuma alagar, mas sem chuva nem aviso agora" |
| Via com histórico < 4 | **0,25** | "provável falso positivo visual" |

**Trânsito** — média dos índices disponíveis (`indice_congestionamento` do frame,
`indice_congestionamento_tomtom`), em rampa:

| Índice médio (0–10) | 0 | 3 | 5,5 | 8 | 10 |
|---|---|---|---|---|---|
| Nota | 0,25 | 0,45 | 0,72 | 0,92 | 0,97 |

Sem nenhum índice: 0,50. Tipo desconhecido: 0,58 ("contexto genérico").

### O prior espacial de alagamento

`data_fusion/historico_alagamento.py` + `data/pontos_alagamento_sp.json` (20 pontos
compilados do histórico do CGE-SP desde 2013 e da camada de Desastres do GeoSampa, no
entorno das câmeras catalogadas).

```text
recorrência "cronico"    → índice base 9,0
recorrência "frequente"  → índice base 6,0
recorrência "ocasional"  → índice base 3,0

peso pleno até 150 m; decai linearmente até 0 em 400 m (haversine)
```

**Esta camada é estática por decisão de escopo.** Ela nunca dispara um evento nem conta
como fonte ao vivo — só calibra a confiabilidade de um alagamento que a câmera já suspeitou.
É o que permite manter a regra "tempo real só vale para detecção via câmera" sem jogar fora
um dado histórico que sabidamente reduz falso positivo.

### Promoção e rebaixamento automáticos

Em `data_fusion_service.aplicar_fusao_evento(persistir=True)`:

- `em_analise` + confiabilidade ≥ limiar → **`ativo`**
- `ativo` + fonte automática (`yolo`) + confiabilidade < limiar → **volta a `em_analise`**
  (um evento YOLO só chega a `ativo` por promoção automática, então pode voltar)

Qualquer mudança de status é logada em `logs_sistema` com os componentes que a
justificaram, e publicada como `evento_atualizado`.

**Detalhe importante — arredondamento:** a comparação usa a confiabilidade **exibida**, não
o float cru. Um evento de 0,7977 aparece como "80%" no painel, e a regra "80% na tela vira
ativo" mentiria se comparasse 0,7977 < 0,80. O backend usa
`Decimal(str(v)).quantize(0.01, ROUND_HALF_UP)`; o frontend usa
`Number(v.toFixed(2))` — os dois critérios são equivalentes de propósito
(`data_fusion_service.atinge_limiar_ativo` ↔ `fusion-format.atingeLimiarAtivo`), senão o
veredito do painel contradiz o status do evento.

### Rede de segurança

`promover_eventos_por_confiabilidade` roda no startup e a cada 120 s sobre todos os eventos
abertos, recalculando e ajustando o status. Cobre o que só mudaria num recálculo posterior:
limiar alterado, dado de contexto que chegou depois da criação.

---

## 13. Ciclo de vida de um evento

```text
            detecção contínua
            (câmera CET, sem humano)
                      │
                      ▼
              status = "em_analise"
              confianca = confiança da detecção
                      │
                      │  Data Fusion (na criação e a cada 120 s)
                      ▼
        ┌─────────────────────────────┐
        │ confiabilidade ≥ 0,77 ?     │
        └───────┬─────────────┬───────┘
             sim│             │não
                ▼             ▼
           "ativo"      permanece "em_analise"
                │             │      (some do painel com o filtro padrão)
                └──────┬──────┘
                       │  nova detecção no mesmo ponto → detectado_em renovado
                       │
                       ▼
        detectado_em < agora − 45 min
                       │
                       ▼
        APAGADO do banco (evento, evidências, dados
        contextuais, localização órfã) + broadcast
        "evento_removido"
```

`event_retention.py` faz três coisas no loop de 120 s:

1. **`purgar_eventos_expirados`** — apaga tudo fora da janela. A remoção é **propagada** por
   WS/SSE: o painel só tira um evento da lista quando recebe `evento_removido`, então apagar
   em silêncio deixava cópias fantasma na tela com o contador acima do que existia no banco.
2. **`colapsar_eventos_duplicados`** — por `(tipo, lat 5 casas, lon 5 casas)`, mantém só o
   mais recente. Rede de segurança para pilhas criadas antes do dedup, por exemplo depois de
   reinícios seguidos do servidor zerando o cooldown em memória.
3. **`promover_eventos_por_confiabilidade`** — ajusta status ao limiar.

Não existe status `resolvido`: não há operador para resolver um evento, e a expiração o
apaga antes (coluna `resolvido_em` removida na migração `006`).
