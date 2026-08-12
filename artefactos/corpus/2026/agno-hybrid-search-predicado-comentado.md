---
tipo: teardown-repo
titulo: El hybrid_search de PgVector tiene el predicado @@ comentado y fusiona escalas incomparables
fecha: 2026-08-12
dominio: recuperacion
temas: [agno, pgvector, hibrido, rrf, fusion, postgres, fts]
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      En vectordb/pgvector/pgvector.py:1157 la línea que aplica el predicado de
      texto completo está comentada - `# stmt = stmt.where(ts_vector.op("@@")(ts_query))`.
    estado: probado
  - texto: >-
      Sin ese predicado la sentencia calcula to_tsvector y una distancia coseno
      para CADA fila de la tabla y ordena por una expresión computada. Ningún
      índice puede servir ese plan.
    estado: probado
  - texto: >-
      El SET LOCAL hnsw.ef_search de la línea 1192 se ejecuta sin ningún efecto,
      porque el plan resultante no usa el índice HNSW.
    estado: probado
  - texto: >-
      La fusión es una suma lineal ponderada, `w * vector_score + (1-w) * text_rank`,
      de dos escalas que no son comparables - una distancia coseno normalizada y
      un ts_rank de Postgres.
    estado: probado
  - texto: >-
      Por tanto peso_vectorial = 0.5 NO significa "mitad y mitad" - significa
      "medio de una escala más medio de otra", que es la patología del tipo de
      cambio - sumar 100 euros y 100 yenes y llamarlo 200.
    estado: extrapolacion
    verificable_por: >-
      Correr las dos consultas por separado sobre el mismo corpus y comparar los
      histogramas de vector_score y text_rank - si sus rangos difieren en un
      orden de magnitud, cualquier w fijo está dominado por una de las dos.
relacionado_con:
  - 2026-08-12-agno-pgvector-indices-decorativos
  - 2026-08-12-rrf-k-60-de-donde-sale-el-sesenta
---

## Qué mirar

`SearchType.hybrid` de Agno promete lo que todo el mundo quiere: una consulta,
dos carriles, un peso para mezclarlos. Lo que hace es otra cosa.

## Las dos averías, que son independientes

**Una.** El predicado `@@` está comentado. `@@` es el operador de Postgres que
pregunta «¿este documento casa con esta consulta de texto?». Sin él, la cláusula
`WHERE` no filtra nada por texto: la consulta recorre la tabla entera, calcula
`to_tsvector(content)` fila a fila —no lo lee de un índice, lo *computa*— y
ordena por una expresión. El planificador no tiene nada que indexar ahí.

**Dos.** Aunque arreglaras la primera, la fusión seguiría rota. Sumar
`0,5 · similitud_coseno + 0,5 · ts_rank` supone que las dos magnitudes viven en
la misma escala. No lo hacen. La similitud coseno normalizada se mueve en
`[0, 1]` con casi todos los valores apretados entre 0,7 y 0,9; el `ts_rank` de
Postgres es una función de frecuencia sin cota superior fija que en la práctica
devuelve números como 0,06. Con esos rangos, `w = 0,5` está en la práctica
mucho más cerca de «solo vectorial» que de «mitad y mitad».

## Qué se hizo en su lugar

Dos consultas separadas y fusión por **RRF** en Python. RRF ignora los scores y
usa solo los **rangos** —el puesto 1, el puesto 2— que es precisamente lo que lo
hace inmune al problema de las escalas. Cuesta una consulta más y ~25 líneas.

## La forma del fallo, que es la que se repite

Un parámetro que se lee como vivo y no lo está. `peso_vectorial` existe, se
puede poner, no da error, y no significa lo que parece. Es la misma clase de
avería que los índices que nadie crea y que el fingerprint ciego al corpus: el
sistema no se rompe, te responde con confianza un número que no vale.
