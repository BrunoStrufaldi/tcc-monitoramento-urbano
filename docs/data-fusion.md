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

### Peso do contexto conforme a concordância

Quando há duas fontes de contexto ao vivo (chuva e INMET, ou contagem de veículos e
TomTom), o peso do contexto é multiplicado por um fator entre 0,8x (as fontes se
contradizem) e 1,4x (dizem a mesma coisa), conforme as notas delas concordam. Uma
diferença de 0,4 ou mais entre as notas conta como contradição total. Com uma fonte só, o
fator é 1,0x. O histórico de alagamento fica fora dessa conta, porque ele fala da via e
não do que está acontecendo agora.

### Níveis

| Confiabilidade | Nível |
|---|---|
| ≥ 0,80 | `alta` |
| 0,55 a 0,79 | `media` |
| < 0,55 | `baixa` |

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

O `promover_eventos_por_confiabilidade` roda quando o sistema inicia e a cada 120 s em
todos os eventos abertos, recalculando e ajustando o status. Isso cobre o que só mudaria
num recálculo depois, como um limite alterado ou um dado de contexto que chegou depois do
evento.

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
                      │  Data Fusion (na criação e a cada 120 s)
                      ▼
        ┌─────────────────────────────┐
        │ confiabilidade ≥ 0,77 ?     │
        └───────┬─────────────┬───────┘
             sim│             │não
                ▼             ▼
           "ativo"      continua "em_analise"
                │             │      (some do painel com o filtro padrão)
                └──────┬──────┘
                       │  nova detecção no mesmo ponto → detectado_em atualizado
                       │
                       ▼
        detectado_em < agora − 45 min
                       │
                       ▼
        APAGADO do banco (evento, evidências, dados
        contextuais, localização sem uso) + aviso
        "evento_removido"
```

O `event_retention.py` faz três coisas a cada 120 s:

1. `purgar_eventos_expirados`: apaga tudo que passou da janela. Cada remoção é avisada por
   WS/SSE, porque o painel só tira um evento da lista quando recebe `evento_removido`.
   Apagar sem avisar deixava cópias velhas na tela, com o contador acima do que existia no
   banco.
2. `colapsar_eventos_duplicados`: para cada `(tipo, lat com 5 casas, lon com 5 casas)`,
   deixa só o evento mais recente. Isso resolve repetições criadas antes da checagem de
   duplicados, por exemplo depois de vários reinícios do servidor, que zeram o tempo de
   espera na memória.
3. `promover_eventos_por_confiabilidade`: ajusta o status conforme o limite.

Não existe o status `resolvido`: não há operador para resolver um evento, e ele é apagado
quando passa o tempo (a coluna `resolvido_em` foi removida na migração `006`).
