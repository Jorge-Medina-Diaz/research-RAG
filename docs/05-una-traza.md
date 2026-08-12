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

**denso** — respaldó 12 de los 12 fragmentos que acabaron entrando

| puesto que tenía aquí | artefacto |
|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 3 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 8 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 10 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 13 | `2026-08-12-getpass-no-falla-se-cuelga` |
| 14 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 16 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` |
| 19 | `2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento` |
| 21 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` |
| 22 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 25 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 30 | `2026-08-12-agno-pgvector-indices-decorativos` |

_Los puestos que faltan son candidatos que este carril colocaba por delante y que el otro no respaldó, así que no sobrevivieron a la fusión._

**lexico** — respaldó 12 de los 12 fragmentos que acabaron entrando

| puesto que tenía aquí | artefacto |
|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` |
| 4 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 5 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 7 | `2026-08-12-agno-hybrid-search-predicado-comentado` |
| 9 | `2026-08-12-agno-pgvector-indices-decorativos` |
| 11 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` |
| 12 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` |
| 13 | `2026-08-12-getpass-no-falla-se-cuelga` |
| 14 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 15 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` |
| 27 | `2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento` |
| 29 | `2026-08-12-agno-pgvector-indices-decorativos` |

_Los puestos que faltan son candidatos que este carril colocaba por delante y que el otro no respaldó, así que no sobrevivieron a la fusión._

## 3 · La fusión (RRF, k=60)

RRF ignora las puntuaciones y usa solo los puestos, que es lo que lo hace
inmune a mezclar escalas incomparables. Un documento que sale en los dos
carriles suma dos veces, así que el **acuerdo** pesa más que un primer
puesto solitario.

| # | artefacto · fragmento | RRF | puesto en cada carril |
|---:|---|---:|---|
| 1 | `2026-08-12-rrf-k-60-de-donde-sale-el-sesenta` · `…73b949` | 0.03279 | denso #1, lexico #1 |
| 2 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…d445c8` | 0.02963 | denso #8, lexico #7 |
| 3 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` · `…72ed46` | 0.02921 | denso #3, lexico #15 |
| 4 | `2026-08-12-agno-pgvector-indices-decorativos` · `…1b9133` | 0.02878 | denso #10, lexico #9 |
| 5 | `2026-08-12-agno-hybrid-search-predicado-comentado` · `…24de86` | 0.02782 | denso #22, lexico #4 |
| 6 | `2026-08-12-getpass-no-falla-se-cuelga` · `…9254a3` | 0.02740 | denso #13, lexico #13 |
| 7 | `2026-08-12-agno-filtros-operadores-anunciados-no-implementados` · `…d7e783` | 0.02724 | denso #16, lexico #11 |
| 8 | `2026-08-12-epocas-para-medir-un-corpus-que-crece` · `…32a65e` | 0.02703 | denso #14, lexico #14 |
| 9 | `2026-08-12-agno-pgvector-indices-decorativos` · `…1edf5e` | 0.02650 | denso #30, lexico #5 |
| 10 | `2026-08-12-ragchecker-la-aritmetica-no-la-dependencia` · `…72330d` | 0.02624 | denso #21, lexico #12 |
| 11 | `2026-08-12-la-configuracion-es-el-tratamiento-no-el-instrumento` · `…f158ec` | 0.02415 | denso #19, lexico #27 |
| 12 | `2026-08-12-agno-pgvector-indices-decorativos` · `…5f6439` | 0.02300 | denso #25, lexico #29 |

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

En esta corrida lo hace el número **2**: salió 8.º en denso y 7.º en lexico, sin ser primero en ninguno, y aun así entra por delante de candidatos mejor situados en un solo carril.

Después de fusionar, esta información ya no existe. Por eso se captura **en el instante de la búsqueda** y se guarda en la tabla `consulta`: sin ella, mover `peso_carril`, cambiar de embedder y tocar el analizador léxico son tres movimientos indistinguibles.

