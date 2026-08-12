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

**denso** — respaldó 11 de los 12 fragmentos que acabaron entrando

| puesto que tenía aquí | artefacto |
|---:|---|
| 8 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 12 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 13 | `2026-08-12-el-carril-de-grafo-construido-y-sin-encender` |
| 14 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 15 | `2026-08-12-plainto-tsquery-hace-and-y-devuelve-cero` |
| 18 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 21 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` |
| 23 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 24 | `2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento` |
| 25 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` |
| 30 | `2026-08-12-agno-env-fingerprint-ciego-al-corpus` |

_Los puestos que faltan son candidatos que este carril colocaba por delante y que el otro no respaldó, así que no sobrevivieron a la fusión._

**lexico** — respaldó 12 de los 12 fragmentos que acabaron entrando

| puesto que tenía aquí | artefacto |
|---:|---|
| 1 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 2 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 3 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 5 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 6 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 10 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` |
| 13 | `2026-08-12-plainto-tsquery-hace-and-y-devuelve-cero` |
| 16 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` |
| 19 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 21 | `2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento` |
| 22 | `2026-08-12-agno-env-fingerprint-ciego-al-corpus` |
| 26 | `2026-08-12-el-carril-de-grafo-construido-y-sin-encender` |

_Los puestos que faltan son candidatos que este carril colocaba por delante y que el otro no respaldó, así que no sobrevivieron a la fusión._

## 3 · La fusión (RRF, k=60)

RRF ignora las puntuaciones y usa solo los puestos, que es lo que lo hace
inmune a mezclar escalas incomparables. Un documento que sale en los dos
carriles suma dos veces, así que el **acuerdo** pesa más que un primer
puesto solitario.

| # | artefacto · fragmento | RRF | puesto en cada carril |
|---:|---|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` · `…13ca98` | 0.03009 | denso #8, lexico #5 |
| 2 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` · `…6164de` | 0.02869 | denso #18, lexico #3 |
| 3 | `2026-08-12-agno-pgvector-indices-decorativos` · `…259f87` | 0.02866 | denso #14, lexico #6 |
| 4 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…7ad543` | 0.02818 | denso #23, lexico #2 |
| 5 | `2026-08-12-plainto-tsquery-hace-and-y-devuelve-cero` · `…094faa` | 0.02703 | denso #15, lexico #13 |
| 6 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` · `…09d1ab` | 0.02663 | denso #21, lexico #10 |
| 7 | `2026-08-12-agno-pgvector-indices-decorativos` · `…d3eae8` | 0.02655 | denso #12, lexico #19 |
| 8 | `2026-08-12-el-carril-de-grafo-construido-y-sin-encender` · `…10bcde` | 0.02533 | denso #13, lexico #26 |
| 9 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` · `…1125d6` | 0.02492 | denso #25, lexico #16 |
| 10 | `2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento` · `…5e097f` | 0.02425 | denso #24, lexico #21 |
| 11 | `2026-08-12-agno-env-fingerprint-ciego-al-corpus` · `…95dd0e` | 0.02331 | denso #30, lexico #22 |
| 12 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…c0f1d8` | 0.01639 | lexico #1 |

De un pool de 40 candidatos por carril salen los **12** que llegan al prompt.

## 4 · La respuesta

```
Segun la memoria, el punto relevante esta recogido en [[art:2026-08-12-rrf-k-60-de-donde-sale-el-sesenta]].
```

## 5 · El veredicto, regla por regla

La spec tiene ocho reglas; cinco las decide código y tres el juez. Una probe no las declara todas: solo las que su caso pone a prueba. Esta declara **3** —R1, R3, R5— y de esas, las que van por código son las de la tabla.

| regla | veredicto | motivo |
|---|:---:|---|
| R1 | ✓ | — |

Las reglas R3, R5 las decide el juez LLM, no el código: dependen de criterio y por eso llevan su propia puerta de calibración.

## 6 · Qué enseña esta traza

- ✓ `2026-08-12-agno-hybrid-search-predicado-comentado`
- ✓ `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta`

**Recall de esta probe: 100%.** Los dos artefactos que hacían falta llegaron, así que si la respuesta falla el problema está en el prompt o en la síntesis, no en la recuperación. Esa distinción es todo el valor del diagnóstico: dice qué palanca tocar.

Y lo que solo se ve aquí: **un artefacto puede ganar sin ser el primero de ningún carril.** RRF suma `1/(k+puesto)` de cada carril, así que el acuerdo entre dos formas distintas de buscar pesa más que la convicción de una sola.

En esta corrida lo hace el número **2**: salió 18.º en denso y 3.º en lexico, sin ser primero en ninguno, y aun así entra por delante de candidatos mejor situados en un solo carril.

Después de fusionar, esta información ya no existe. Por eso se captura **en el instante de la búsqueda** y se guarda en la tabla `consulta`: sin ella, mover `peso_carril`, cambiar de embedder y tocar el analizador léxico son tres movimientos indistinguibles.

