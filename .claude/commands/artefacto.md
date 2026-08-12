---
description: Convierte la conclusión de esta sesión en un artefacto listo para ingerir
argument-hint: "[tipo: nota-investigacion | teardown-repo | lectura-paper | patron | problema-solucion | decision | benchmark]"
allowed-tools: Read, Write(artefactos/entrada/**), Bash(uv:*)
---

Escribe en `artefactos/entrada/` un artefacto con lo que hemos concluido en esta
sesión. Tipo: $1 (si no te dan nada, decídelo tú y dime por qué).

## El contrato

Cinco campos obligatorios, todos de una línea. Lo demás se deriva o es opcional:
la fricción en la ingesta no se paga una vez, se paga en cada artefacto.

```yaml
---
tipo: <uno de los siete>
titulo: <una frase que sea la tesis, no una etiqueta>
fecha: <AAAA-MM-DD>
temas: [<libres, en minúsculas>]
dominio: <recuperacion|evaluacion|agentes|datos|infraestructura|estadistica|producto|otro>
---
```

`dominio` es vocabulario CERRADO y `temas` es libre. No es redundancia: `dominio`
es el único eje sobre el que «relacionar contextos dispares» es computable en
vez de una intuición.

## Lo que el tipo exige

- `teardown-repo` y `lectura-paper` → al menos una `fuentes`. Y si la fuente es
  un repo, **`commit` obligatorio**: un teardown sin commit es inverificable, y
  eso es lo único que aporta.
- `patron` → di también cuándo NO aplica. Un patrón sin alcance negativo es un
  eslogan.
- `problema-solucion` → síntoma, causa raíz, solución.
- `decision` → contexto, decisión, y **las alternativas descartadas**. Sin ellas
  no es una decisión, es un hecho.
- `benchmark` → cada medida con su `n` y sus condiciones, y si la corriste tú o
  la reportan sus autores.

## `afirmaciones` — la parte que más rinde

Es opcional, y es lo que más vale. Se indexa por delante del cuerpo: son la
tesis destilada, y sin ellas el corpus indexa la prosa y tira el resumen.

```yaml
afirmaciones:
  - texto: <una afirmación, completa y autocontenida>
    estado: probado | reportado | extrapolacion | conjetura
    verificable_por: <cómo se comprobaría — OBLIGATORIO si es extrapolacion>
```

El estado es la nota de honestidad intelectual hecha esquema, y no es
decorativo: hay una regla de la spec (R7) que obliga a la respuesta a propagarlo,
y se comprueba por código.

- `probado` — lo medí o lo leí en el código.
- `reportado` — lo dicen sus autores. Cifra ajena, sin réplica.
- `extrapolacion` — lo deduzco. Necesita `verificable_por`, o es una conjetura
  con otra etiqueta.
- `conjetura` — sospecho.

## `supera`

Si este artefacto corrige a uno anterior, decláralo:

```yaml
supera: [<id-del-artefacto-viejo>]
```

**Escribirlo ES la firma humana.** Cierra la ventana de validez del viejo, que
sigue en la base pero sale de la búsqueda. No lo borra nada, nunca. Y ninguna
otra cosa invalida un artefacto automáticamente.

## Estructura del cuerpo

Tres secciones, y la tercera es la que separa una nota útil de un resumen:

```markdown
## Qué encontré
## Lo que me llevo      <- el patrón general, no el caso concreto
## Lo que NO dice       <- los límites. Lo que no medí, lo que no repliqué.
```

## Antes de terminar

Corre `uv run rag ingerir --no-mover` y enséñame el resultado. Si lo rechaza, el
motivo dice exactamente qué falta. **No arregles el rechazo relajando el
contenido**: el contrato existe porque los filtros de metadatos son la palanca
más barata del retrieval y nacen de aquí.
