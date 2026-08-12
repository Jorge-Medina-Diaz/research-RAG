# Una consulta, de punta a punta

Generado con `uv run rag traza`. Todo lo de abajo salió de una ejecución
real contra el corpus del repo, con el embedder determinista y el modelo
guionizado — sin ninguna clave de API.

## 1 · La pregunta

> Si la fusión de Agno suma escalas incomparables, ¿de dónde saqué el número concreto que uso en la mía?

Probe `P-32` · categoría `multi_hop` · clase `dependiente`

Artefactos que **debían** llegar:

- `2026-08-12-agno-hybrid-search-predicado-comentado`
- `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta`

## 2 · Los dos carriles, por separado

Cada carril busca a su manera y produce su propio orden. Este es el dato
que deja de existir en cuanto se fusiona, y sin él `peso_carril`, el
embedder y el analizador léxico son tres movimientos indistinguibles.

**denso** — 12 de los 12 finales venían de aquí

| puesto en su carril | artefacto |
|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 3 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 7 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 9 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 11 | `2026-08-12-un-detector-que-siempre-dispara-esta-apagado` |
| 12 | `2026-08-12-getpass-no-falla-se-cuelga` |
| 13 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 14 | `2026-08-12-agno-pgvector-indices-decorativos` |

**lexico** — 12 de los 12 finales venían de aquí

| puesto en su carril | artefacto |
|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 3 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 5 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 7 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 9 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 10 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` |
| 11 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` |
| 12 | `2026-08-12-getpass-no-falla-se-cuelga` |

## 3 · La fusión (RRF, k=60)

RRF ignora las puntuaciones y usa solo los puestos, que es lo que lo hace
inmune a mezclar escalas incomparables. Un documento que sale en los dos
carriles suma dos veces, así que el **acuerdo** pesa más que un primer
puesto solitario.

| # | artefacto · fragmento | RRF | puesto en cada carril |
|---:|---|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` · `…d25fd6` | 0.03279 | denso #1, lexico #1 |
| 2 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…d35f0b` | 0.02985 | denso #7, lexico #7 |
| 3 | `2026-08-12-agno-pgvector-indices-decorativos` · `…87f52f` | 0.02899 | denso #9, lexico #9 |
| 4 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…6b5f41` | 0.02822 | denso #21, lexico #3 |
| 5 | `2026-08-12-getpass-no-falla-se-cuelga` · `…ccb283` | 0.02778 | denso #12, lexico #12 |
| 6 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` · `…9da64b` | 0.02764 | denso #3, lexico #25 |
| 7 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` · `…3e1340` | 0.02762 | denso #15, lexico #10 |
| 8 | `2026-08-12-agno-pgvector-indices-decorativos` · `…0780fa` | 0.02662 | denso #29, lexico #5 |
| 9 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` · `…5c4edf` | 0.02659 | denso #20, lexico #11 |
| 10 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` · `…a671b9` | 0.02589 | denso #13, lexico #22 |
| 11 | `2026-08-12-un-detector-que-siempre-dispara-esta-apagado` · `…65b653` | 0.02571 | denso #11, lexico #26 |
| 12 | `2026-08-12-agno-pgvector-indices-decorativos` · `…a89e8b` | 0.02463 | denso #14, lexico #30 |

De un pool de 40 candidatos por carril salen los **12** que llegan al prompt.

## 4 · La respuesta

```
Segun la memoria, el punto relevante esta recogido en [[art:2026-08-12-rrf-k-60-de-donde-sale-el-sesenta]].
```

## 5 · El veredicto, regla por regla

Cinco de las ocho reglas las decide código, no el juez. Una regla que
necesita criterio para saber si se cumple no es una regla.

| regla | veredicto | motivo |
|---|:---:|---|
| R1 | ✓ | — |

Las reglas R3, R5 las decide el juez LLM, no el código: dependen de criterio y por eso llevan su propia puerta de calibración.

## 6 · Qué enseña esta traza

- ✓ `2026-08-12-agno-hybrid-search-predicado-comentado`
- ✓ `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta`

**Recall de esta probe: 100%.** Los dos artefactos que hacían falta llegaron, así que si la respuesta falla el problema está en el prompt o en la síntesis, no en la recuperación. Esa distinción es todo el valor del diagnóstico: dice qué palanca tocar.

Y lo que solo se ve aquí: **un artefacto puede ganar sin ser el primero de ningún carril.** RRF suma `1/(k+puesto)` de cada carril, así que salir séptimo en denso y octavo en léxico vence a salir tercero en uno solo. El acuerdo entre dos formas distintas de buscar es una señal más fuerte que la convicción de una.

Después de fusionar, esta información ya no existe. Por eso se captura **en el instante de la búsqueda** y se guarda en la tabla `consulta`: sin ella, mover `peso_carril`, cambiar de embedder y tocar el analizador léxico son tres movimientos indistinguibles.

