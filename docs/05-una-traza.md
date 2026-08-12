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
| 5 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 7 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 9 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 12 | `2026-08-12-getpass-no-falla-se-cuelga` |
| 13 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 15 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` |

**lexico** — 12 de los 12 finales venían de aquí

| puesto en su carril | artefacto |
|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 4 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 5 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 6 | `2026-08-12-plainto-tsquery-hace-and-y-devuelve-cero` |
| 8 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 9 | `2026-08-12-getpass-no-falla-se-cuelga` |
| 10 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` |
| 11 | `2026-08-12-agno-pgvector-indices-decorativos` |

## 3 · La fusión (RRF, k=60)

RRF ignora las puntuaciones y usa solo los puestos, que es lo que lo hace
inmune a mezclar escalas incomparables. Un documento que sale en los dos
carriles suma dos veces, así que el **acuerdo** pesa más que un primer
puesto solitario.

| # | artefacto · fragmento | RRF | puesto en cada carril |
|---:|---|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` · `…d25fd6` | 0.03279 | denso #1, lexico #1 |
| 2 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…d35f0b` | 0.02963 | denso #7, lexico #8 |
| 3 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` · `…9da64b` | 0.02939 | denso #3, lexico #14 |
| 4 | `2026-08-12-agno-pgvector-indices-decorativos` · `…87f52f` | 0.02858 | denso #9, lexico #11 |
| 5 | `2026-08-12-getpass-no-falla-se-cuelga` · `…ccb283` | 0.02838 | denso #12, lexico #9 |
| 6 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…6b5f41` | 0.02797 | denso #21, lexico #4 |
| 7 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` · `…3e1340` | 0.02722 | denso #15, lexico #12 |
| 8 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` · `…94eb7b` | 0.02688 | denso #5, lexico #27 |
| 9 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` · `…a671b9` | 0.02686 | denso #13, lexico #16 |
| 10 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` · `…5c4edf` | 0.02679 | denso #20, lexico #10 |
| 11 | `2026-08-12-agno-pgvector-indices-decorativos` · `…0780fa` | 0.02675 | denso #28, lexico #5 |
| 12 | `2026-08-12-plainto-tsquery-hace-and-y-devuelve-cero` · `…8bf237` | 0.02626 | denso #30, lexico #6 |

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

