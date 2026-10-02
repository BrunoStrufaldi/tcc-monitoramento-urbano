# Frontend

[← voltar ao README](../README.md#documentação)

## 15. Frontend

TypeScript compilado por `tsc` (`strict: true`, `noEmitOnError`) para ES2020 nativo — sem
bundler, sem framework. `dist/` é versionado.

### Mapa

Leaflet 1.9.4 (via unpkg, com SRI) + camada WMS do **GeoSampa** (`MapaBase_Politico`,
atribuição PMSP), zoom 10–19. Se o Leaflet não carregar, o painel degrada para uma tela de
"Mapa indisponível" e **todo o resto continua funcionando**.

Marcadores são coloridos por status (verde = ativo, amarelo = em análise), agrupados em
cluster conforme o zoom, e a seleção é preservada entre atualizações.

### Views

| View | Estado |
|---|---|
| `dashboard` (Início) | KPIs de status, evento selecionado com anel de confiança, explicação da fusão ("como o score foi calculado") e, no celular em retrato, a evidência visual |
| `yolo-teste` | Testar uma imagem contra os dois modelos de uma vez |

A barra de ícones (`rail`) expõe exatamente esses dois destinos. O painel direito mostra a
evidência visual (imagem anotada pelo YOLO) do evento selecionado, com visualizador ampliado.

### Testador de YOLO

Envia a mesma imagem para `/deteccao/incidente` e `/deteccao/imagem` em paralelo e emite um
veredito legível:

- alagamento detectado → **danger**
- veículos ≥ `min_veiculos_transito` (lido de `/deteccao/status`) → **warn**
- nada relevante → **ok**

Desenha as caixas sobre a imagem e lista cada detecção indicando de qual modelo veio.

### Filtros e KPIs

O filtro de status (Todos / Ativos / Em análise) inicia forçado em **Todos** — o navegador
pode restaurar a seleção anterior do `<select>`, então o código sobrescreve no boot. No
celular o mesmo filtro aparece como botões no painel lateral, sincronizados com o `<select>`.

### Design tokens (CSS)

**Marca**

| Token | Valor |
|---|---|
| `--gx` | `#FF5500` |
| `--gx-light` | `#FF8A00` |
| `--gx-dim` | `rgba(255,138,0,0.10)` |

**Superfícies (sólidas, sem transparência)**

| Token | Valor | Uso |
|---|---|---|
| `--bg-base` | `#0C0C0C` | fundo |
| `--bg-panel` | `#111111` | painéis |
| `--bg-raised` | `#161616` | elevado |
| `--bg-card` | `#1A1A1A` | cards |
| `--bg-input` | `#0F0F0F` | campos |
| `--bg-hover` | `#1E1E1E` | hover |
| `--bg-active` | `#222222` | active |

**Semânticos**

| Token | Valor | Uso |
|---|---|---|
| `--ok` | `#2EAA5A` | sucesso, ativo |
| `--warn` | `#E6A817` | atenção, médio |
| `--danger` | `#DC3545` | erro, crítico |
| `--info` | `#4A90D9` | informação |

### Acessibilidade e responsividade

- `prefers-reduced-motion: reduce` desliga todas as animações
- `:focus-visible` com outline laranja (foco só por teclado, não por clique)
- Skip link "Pular para o painel de eventos", `aria-label` em botões e seções, `aria-live` nas
  regiões que atualizam sozinhas
- Breakpoints: 1200px (painel direito vira drawer), 980px (sidebar oculta, mapa cheio),
  680px (layout mobile), 480px (KPIs em uma coluna)
- Validado de 320×568 a 1920×1080 e em zoom de 80% a 150%
- Estados vazios explícitos: nenhum evento selecionado, evento sem confiança, sem
  evidência, API indisponível, WebSocket caído
