# Spec del cerebro

Esta es la **función objetivo** del bucle de auto-mejora. El bucle no persigue
«que responda mejor»: persigue que cada regla de aquí se cumpla, medida sobre el
golden set a una época fija. Si una regla no se puede comprobar mecánicamente,
no es una regla: es un deseo, y sale de este documento.

Cuando el bucle edita el diseño, **este fichero no se toca**. Es el punto fijo
hacia el que converge. Cambiarlo es cambiar el objetivo, y eso lo decides tú.

Y hay un mecanismo detrás de esa frase, no solo la frase: el sha256 de este
fichero entra en el `digest()` del scorer, y el digest entra en la huella del
entorno. Si cambia, toda comparación con mediciones anteriores queda marcada
como ilegal. **El escalón 6 no está prohibido por educación: está impedido por
el tipo de dato.**

---

## Qué es el cerebro

Una memoria de I+D. El corpus son artefactos que escribo yo: conclusiones de
sesiones de investigación, desmontajes de repos, lecturas de papers, patrones
extraídos, problemas con su solución y decisiones.

Su valor no está en sonar bien, sino en dos cosas: **no inventarse una relación
entre dos notas mías**, y **no servir como vigente algo que yo mismo corregí
después**. Los dos fallos se componen: una respuesta equivocada entra en el
siguiente artefacto que escribo, y el corpus se autocontamina.

---

## Reglas

Cada regla lleva su identificador y su línea *Comprobable*. Los probes se
etiquetan con ella y el reporte del bucle agrupa los fallos por regla.

Cinco de las ocho las comprueba **código**, no el juez. Menos superficie de
sesgo, menos coste, y el nivel determinista corre offline y sin claves.

### R1 · Toda afirmación cita su artefacto

Cada afirmación factual cita el artefacto del que sale, con su identificador
estable, en la forma `[[art:mi-id]]`. Si una respuesta combina dos artefactos,
cita los dos.

*Comprobable* (código): la respuesta contiene al menos una cita que case
`\[\[art:[a-z0-9\-]+\]\]`, y todo id citado está entre los artefactos
recuperados en esa consulta.

### R2 · Si no está en el contexto, se dice

Cuando el contexto recuperado no contiene la respuesta, el cerebro responde
exactamente: **«No lo tengo en la memoria.»** Sin matizar, sin aproximar, sin
sugerir dónde podría estar.

*Comprobable* (código): igualdad literal de la cadena tras normalizar espacios,
y ausencia de cualquier texto adicional.

### R3 · Nunca memoria paramétrica

El cerebro no usa lo que el modelo sabe del mundo. Si la pregunta versa sobre
algo que no está en los artefactos recuperados, aplica R2.

*Comprobable* (juez): ninguna entidad, cifra ni referencia de la respuesta que
no aparezca en los fragmentos recuperados.

### R4 · Los literales se reproducen literales

Números, versiones, identificadores de arXiv, nombres de símbolo
(`hnsw.ef_search`), rutas y nombres de fichero se reproducen tal cual figuran.
No se redondean, no se normalizan, no se abrevian.

*Comprobable* (código): todo token de la respuesta que case
`\d[\d.,]*|v?\d+\.\d+(\.\d+)?|arXiv:\d{4}\.\d{4,5}|[a-z_]+\.[a-z_]+` aparece
literalmente en algún fragmento recuperado.

### R5 · No fundir dos artefactos en una afirmación que ninguno sostiene

Relacionar artefactos es el producto. Presentar la relación como un hecho
documentado, no.

*Comprobable* (juez): para cada afirmación que cite dos o más artefactos, o bien
uno de ellos la sostiene por sí solo, o bien la respuesta la marca como
inferencia con una fórmula de la lista cerrada {«relacionando», «cruzando», «se
sigue de», «inferencia mía»}.

### R6 · Lo superado se marca

Si un artefacto posterior declara `supera` al que responde, el cerebro da el
vigente **y** nombra el que lo superó.

*Comprobable* (código + juez): cuando algún artefacto recuperado declara
`supera: <id>` y `<id>` también aparece, la respuesta contiene el identificador
del artefacto corrector, y no presenta el valor antiguo como vigente.

### R7 · El estatus epistémico se propaga

Si el artefacto marca la afirmación como extrapolación, conjetura o cifra
auto-reportada, la respuesta lo dice.

*Comprobable* (código): si algún fragmento recuperado que sostiene la respuesta
lleva la marca `[extrapolacion]`, `[conjetura]` o `[reportado]`, la respuesta
contiene al menos un marcador de la lista cerrada {«extrapolación»,
«conjetura», «auto-reportado», «sin verificar», «sin réplica independiente»}.

### R8 · Sin relleno

Sin introducción, sin resumen final, sin cortesía. Empieza por el dato. Máximo
ocho frases, salvo que la pregunta pida enumerar.

*Comprobable* (código): recuento de frases ≤ 8, y ausencia de fórmulas de
cortesía de una lista cerrada.

---

## Reglas descartadas por no ser comprobables

Este bloque es obligatorio: es donde se ve que el criterio se aplicó de verdad.

- **«La respuesta es accionable»** — exige criterio humano. Fuera.
- **«Sugiere el artefacto relacionado más útil»** — «útil» no tiene línea
  *Comprobable* posible sin un segundo juez, y un juez que juzga al juez es el
  escalón 6.
- **«No repite lo que ya sé»** — exigiría un modelo de mi estado de conocimiento
  que el sistema no tiene. Fuera.

---

## Categorías de probe

Seis. Cada una **falla por un motivo distinto** y por tanto se arregla con una
palanca distinta; un conjunto que no las cubra todas deja al bucle sin señal
para diagnosticar.

| Categoría | Qué prueba | Palanca típica |
|---|---|---|
| `single_hop` | Un dato que está en un solo artefacto | ninguna, debe pasar de salida |
| `multi_hop` | Exige cruzar dos artefactos — **el producto** | `top_k`, `top_k_por_carril` |
| `aggregation` | Síntesis sobre muchos artefactos | `top_k`, `pool_fusion` |
| `lexical_exact` | Identificadores casi idénticos: `2.8.6` frente a `2.8.x`, `ef_search` frente a `ef_construction` | `fts_modo`, `peso_carril`, `reranker` |
| `temporal` | Un artefacto posterior corrige a uno anterior | `instrucciones` (R6), `solo_vigentes` |
| `fuera_de_alcance` | La respuesta no está — **el freno** | `instrucciones` (R2) |

Y dos clases transversales que deciden si una probe sobrevive al crecimiento del
corpus:

- **`invariante`** — la conducta se cumple pase lo que pase con el corpus (la
  forma exacta de R2, el formato de cita, la reproducción literal de cifras).
  Son el suelo estable de la señal y el grueso del holdout, que nadie mira y por
  tanto nadie puede revalidar.
- **`dependiente`** — necesita artefactos concretos, declarados en `requiere`.
  Si uno deja de estar vigente, la probe se **suspende, no falla**.

---

## Suelos

Un cambio se acepta solo si, además de mejorar lo que perseguía, ninguno de
estos cae. Métrica primaria única y el resto como restricciones: nunca una suma
ponderada, porque los pesos definen un tipo de cambio entre métricas y el
optimizador lo usará para maximizar el número sacrificando lo que querías
proteger.

| Métrica | Suelo | Por qué |
|---|---|---|
| `recall@top_k` (**primaria**) | ≥ 0,85 | Si el fragmento no llega, no hay prompt que lo salve |
| R4 · literales | **0 violaciones** | Sin margen. Y aquí el fallo se compone: una versión mal citada entra en el siguiente artefacto que escribo |
| R2 · abstención | **0 fallos** en `fuera_de_alcance` | Inventar es peor que no responder |
| R5 · no fusión | **0 violaciones** | Es el modo de fallo característico del producto |
| R6 · lo superado | ≥ 0,95 | Conocimiento superado servido como vigente es la peor salida de una memoria viva |
| Latencia p95 | ≤ 8 s | Por encima dejo de usarlo, y así mueren las herramientas personales |

**Los suelos que importan van en recuento, no en tasa.** Con n ≈ 30-60 probes el
semiancho del intervalo de confianza al 95 % ronda ±13-16 puntos: un suelo de
«0,85» no es exigible porque el instrumento no lo distingue de 0,72. Cero
violaciones sí es exigible a cualquier n.

**Y una violación tiene que reproducirse.** R4 a cero sobre 30 probes con un
juez al ~95 % de auto-consistencia da una probabilidad cercana al 78 % de al
menos una violación espuria por corrida: el suelo más importante bloquearía la
promoción a cara o cruz y el bucle gastaría rondas persiguiendo fantasmas. Al
detectar una violación se re-corre **solo esa probe** a k=3 y se exige ≥2/3.

---

## Lo que el bucle NO puede tocar

- Este fichero.
- El juez (`cerebro/juez.py`) y el scorer.
- El corpus de `artefactos/`.
- Los suelos de la tabla anterior.
- La época de medición.
- El holdout, que vive en su propio esquema de Postgres con los permisos
  revocados para el rol de la aplicación — no en una carpeta, porque una
  carpeta la lee cualquier `uv run python -c`.
- `embedder` y `embedder_dim`: cambiarlos obliga a re-embeber el corpus entero.
  Puede proponerlos; aplicarlos lo firmas tú.

**Y una restricción que no es de permisos sino de método:** las palancas de
GENERACIÓN —hoy solo `instrucciones`— el bucle las **propone** y las firmas tú.
Un golden set mayoritariamente sintético ordena bien configuraciones de
recuperación y **no** ordena bien arquitecturas de generación. Mientras el
golden set no tenga ≥40 probes minadas de tráfico real con etiqueta mía, mover
`instrucciones` automáticamente sería optimizar contra una medida que no
distingue.
