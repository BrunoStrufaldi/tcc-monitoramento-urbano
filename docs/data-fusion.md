# Data Fusion e ciclo de vida do evento

[← voltar ao README](../README.md#documentação)

## 12. Data Fusion (confiabilidade)

O módulo `data_fusion/` é Python puro e não depende do FastAPI, então pode ser testado
separado.

### As duas dimensões

| Dimensão | Peso | Fonte |
|---|---|---|
| IA | 4/7 ≈ 57% | `evidencias_visuais`: a maior confiança do YOLO no evento, e se há um modelo registrado |
| Contexto | 3/7 ≈ 43% | `dados_contextuais` com `categoria = contexto`. No alagamento: chuva (Open-Meteo), aviso do INMET e histórico da via. No trânsito: índice de veículos da imagem e TomTom |

Antes eram três dimensões: IA 40%, clima 30% e fonte oficial 30% (calculada pelo
`fontes_dados.tipo` do evento). Como todo evento vem de uma fonte `yolo`, que já conta na
IA, a fonte oficial dava sempre 0, e a divisão dos pesos ficava exatamente em IA 57% e
contexto 43%. A dimensão saiu e os pesos passaram a ser esses 4:3 direto. As notas
continuaram iguais (conferido em 620 cenários). O aviso do INMET, que é a fonte oficial de
verdade, entra como um dos dados do contexto.

### Normalização de peso

Uma dimensão com nota `0` quer dizer "não usada", e não "ruim". O peso dela passa para a
outra:

```python
peso_disponivel = soma dos pesos das dimensões com pontuação > 0
peso_efetivo(d) = PESO[d] / peso_disponivel
confiabilidade  = Σ pontuacao(d) × peso_efetivo(d)
```

Sem nenhum dado de contexto, a confiabilidade é a própria nota da IA.

Fora esse caso, os pesos são fixos: com as duas dimensões presentes a conta é sempre
`C = 0,57 · S_IA + 0,43 · S_ctx`, tenha o contexto uma fonte ou duas. Quando há duas
fontes de contexto (chuva e INMET, ou contagem de veículos e TomTom), elas entram na nota
do contexto pela média, e não mudam o peso.

Até 19/11/2026 o peso do contexto variava de 0,8x a 1,4x conforme as duas fontes
concordavam. Isso foi tirado para o sistema fazer exatamente o que a fórmula diz. No
replay sintético só o A2 mudou, de 0,91 para 0,89, e nenhum status mudou.

### Níveis

| Confiabilidade | Nível |
|---|---|
| ≥ 0,80 | `alta` |
| 0,55 a 0,79 | `media` |
| < 0,55 | `baixa` |

O nível também usa a confiabilidade arredondada para duas casas, como a promoção para
ativo (ver abaixo). O círculo do evento selecionado usa as mesmas faixas: verde a partir
de 80%, amarelo de 55% a 79% e vermelho abaixo de 55%.

### Pontuação do contexto, por tipo de evento

As notas são calculadas ligando pontos de referência com retas, então cada pequena
mudança no valor muda um pouco a nota. Nas pontas a nota para de subir ou descer.

Alagamento: junta até três dados.

```text
chuva medida (Open-Meteo)               aviso INMET ativo (por nível)
  pontos (mm/h → nota):                   grande perigo → 0,93
  0 → 0,30   5 → 0,55   15 → 0,78          perigo        → 0,80
  30 → 0,93  50 → 0,97                     perigo pot.   → 0,60
                                           sem aviso     → 0,40
        └──────────── média dos que existem ──────────┘
                          │
                          ▼
        ajuste pelo histórico da via
          índice ≥ 7 → × 1,12   (alaga quase sempre)
          índice ≥ 4 → × 1,06   (alaga com frequência)
          índice > 0 → × 1,00   (histórico baixo)
          índice = 0 → × 0,90   (via sem histórico, um pouco de cautela)
```

Chuva medida de 0,0 mm/h conta como "sem chuva", e não como uma leitura. Se não houver
chuva nem aviso ativo (só o que o modelo viu), o histórico decide sozinho:

| Situação | Pontuação | Leitura |
|---|---|---|
| Sem a informação de histórico | 0,45 | genérico |
| Via com histórico ≥ 4 | 0,45 | "costuma alagar, mas sem chuva nem aviso agora" |
| Via com histórico < 4 | 0,25 | "provável falso positivo visual" |

Trânsito: média dos índices que existirem (`indice_congestionamento` da imagem e
`indice_congestionamento_tomtom`), com a mesma ideia de pontos de referência:

| Índice médio (0 a 10) | 0 | 3 | 5,5 | 8 | 10 |
|---|---|---|---|---|---|
| Nota | 0,25 | 0,45 | 0,72 | 0,92 | 0,97 |

Sem nenhum índice a nota é 0,50. Para um tipo desconhecido, 0,58 ("contexto genérico").

### O prior espacial de alagamento

Fica em `data_fusion/historico_alagamento.py` e `data/pontos_alagamento_sp.json`: 20
pontos tirados do histórico do CGE-SP (desde 2013) e da camada de Desastres do GeoSampa,
em volta das câmeras do catálogo.

```text
recorrência "cronico"    → índice base 9,0
recorrência "frequente"  → índice base 6,0
recorrência "ocasional"  → índice base 3,0

peso total até 150 m; diminui em linha reta até 0 em 400 m (haversine)
```

Esse histórico é fixo por decisão de escopo. Ele nunca cria um evento e não conta como
fonte ao vivo: só ajusta a confiabilidade de um alagamento que a câmera já viu. Assim o
projeto mantém a regra de "tempo real só pela câmera" sem perder um dado que ajuda a
reduzir os falsos positivos.

### Promoção e rebaixamento automáticos

Em `data_fusion_service.aplicar_fusao_evento(persistir=True)`:

- `em_analise` com confiabilidade ≥ limite → passa para `ativo`
- `ativo` vindo do YOLO com confiabilidade < limite → volta para `em_analise`
  (um evento do YOLO só chega a `ativo` pela promoção automática, então ele pode voltar)

Toda mudança de status é registrada em `logs_sistema`, com as notas que levaram a ela, e
publicada como `evento_atualizado`.

Um detalhe importante é o arredondamento: a comparação usa a confiabilidade que aparece na
tela, e não o número exato. Um evento de 0,7977 aparece como "80%" no painel, e a regra
"80% na tela vira ativo" estaria errada se comparasse 0,7977 com 0,80. O backend usa
`Decimal(str(v)).quantize(0.01, ROUND_HALF_UP)` e o frontend usa `Number(v.toFixed(2))`.
Os dois dão o mesmo resultado de propósito
(`data_fusion_service.atinge_limiar_ativo` e `fusion-format.atingeLimiarAtivo`), senão o
painel mostraria um resultado diferente do status do evento.

### Rede de segurança

A fusão é recalculada a cada ciclo de monitoramento (10 min) em todo evento que a câmera
confirma, com a foto e os dados de contexto daquele ciclo. É isso que permite um evento
`em_analise` virar `ativo` (ou o contrário) sem criar outro evento. Além disso, o
`promover_eventos_por_confiabilidade` roda quando o sistema inicia, para aplicar um limite
que tenha sido alterado na configuração.

---

## 13. Ciclo de vida de um evento

```text
            detecção contínua
            (câmera CET, sem pessoa)
                      │
                      ▼
              status = "em_analise"
              confianca = confiança da detecção
                      │
                      │  Data Fusion (na criação e a cada ciclo que confirma)
                      ▼
        ┌─────────────────────────────┐
        │ confiabilidade ≥ 0,80 ?     │
        └───────┬─────────────┬───────┘
             sim│             │não
                ▼             ▼
           "ativo"      continua "em_analise"
                │             │      (some do painel com o filtro padrão)
                └──────┬──────┘
                       │  ciclo geral (10 min) vê de novo → mesmo evento com
                       │  foto e contexto novos, fusão recalculada, detectado_em
                       │  atualizado (pode subir para "ativo" ou voltar)
                       │
                       ▼
        2 ciclos gerais seguidos sem ver o evento
                       │
                       ▼
        APAGADO do banco (evento, evidências, dados
        contextuais, localização sem uso) + aviso
        "evento_removido"
```

Quem apaga o evento é o ciclo de monitoramento, no 2º ciclo geral seguido sem confirmação
([deteccao.md](deteccao.md)). Não existe prazo de validade: se a câmera parar de mandar
imagem, o evento fica no mapa até ela voltar. O `event_retention.py` faz a remoção em si:

1. `remover_eventos`: apaga o evento e o que está ligado a ele. Cada remoção é avisada por
   WS/SSE, porque o painel só tira um evento da lista quando recebe `evento_removido`.
   Apagar sem avisar deixava cópias velhas na tela, com o contador acima do que existia no
   banco.
2. `colapsar_eventos_duplicados`: roda no fim de cada passada e, para cada
   `(tipo, lat com 5 casas, lon com 5 casas)`, deixa só o evento mais recente. O ciclo já
   atualiza o evento no lugar em vez de criar outro, então isto é só uma garantia.

Não existe o status `resolvido`: não há operador para resolver um evento, e ele é apagado
quando a câmera deixa de ver (a coluna `resolvido_em` foi removida na migração `006`).
