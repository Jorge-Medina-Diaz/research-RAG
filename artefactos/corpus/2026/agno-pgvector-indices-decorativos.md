---
tipo: teardown-repo
titulo: En Agno 2.8.6, PgVector nunca crea sus índices y la búsqueda híbrida escanea la tabla entera
fecha: 2026-08-12
dominio: recuperacion
temas: [agno, pgvector, indices, hnsw, busqueda-hibrida, fallo-silencioso]
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
afirmaciones:
  - texto: >-
      PgVector.create() no crea el índice HNSW ni el GIN. Solo los crea
      optimize(), y nada en agno/knowledge/ ni en agno/vectordb/pgvector/ llama
      a optimize(); el único llamador del paquete es singlestore.py:116.
    estado: probado
  - texto: >-
      _create_gin_index interpola content_language sin comillas y emite
      to_tsvector(spanish, content), que Postgres resuelve como columna y falla.
    estado: probado
  - texto: >-
      hybrid_search tiene su predicado @@ comentado en pgvector.py:1157, así que
      calcula to_tsvector y la distancia coseno para cada fila de la tabla y
      ordena por una expresión computada. Ningún índice puede servir ese plan.
    estado: probado
  - texto: >-
      La fusión híbrida es una suma lineal ponderada de un coseno y un
      ts_rank_cd normalizado, dos escalas que no son comparables. peso_vectorial
      = 0.5 no significa "mitad y mitad" y no tiene punto medio interpretable.
    estado: probado
  - texto: >-
      Un pipeline que declare hnsw_m o hnsw_ef_search como palancas sobre una
      instalación de Agno sin índices creados a mano está moviendo parámetros
      sobre un índice que no existe.
    estado: extrapolacion
    verificable_por: >-
      EXPLAIN sobre una consulta de similitud tras un insert limpio: si aparece
      Seq Scan y no Index Scan using ..._hnsw, no hay índice.
---

## Qué encontré

Leyendo el paquete instalado, no la documentación.

`PgVector.create()` (`pgvector.py:226`) crea la extensión, el esquema y la tabla
con cuatro índices btree sobre `id`, `name`, `content_hash` y `content_id`. Nada
más. `_create_vector_index` y `_create_gin_index` existen, funcionan, y solo se
llaman desde `optimize()` (`:1273`) — al que nadie llama.

El GIN además está roto para configuraciones no inglesas: `:1462` emite

    CREATE INDEX ... USING GIN (to_tsvector({self.content_language}, content));

sin comillas alrededor del idioma. Con `content_language="spanish"` eso es
`to_tsvector(spanish, content)`, y `spanish` desnudo es un identificador que
Postgres busca como columna.

Y `hybrid_search` tiene comentada la línea que lo haría usable:

    # stmt = stmt.where(ts_vector.op("@@")(ts_query))

## Lo que me llevo

Es la misma clase de defecto que la navaja de Apache AGE que me dejó el modelo
bi-temporal decorativo en Universo Profesional: **un parámetro que se lee como
vivo y no lo está**. No lanza ningún error. El sistema responde. Los números
suben y bajan. Y la palanca no está conectada a nada.

El patrón general: cuando una librería expone un parámetro cuyo efecto no puedo
observar directamente, el trabajo no es leer la documentación, es escribir la
comprobación que falla si el parámetro está desconectado. Aquí es un `\d+` sobre
la tabla, o un `EXPLAIN`.

## Lo que NO dice

No he medido cuánto cuesta el escaneo completo. A ~10^3 fragmentos es
irrelevante (decenas de milisegundos). No sé dónde está el codo; la estimación
de 10^4-10^5 es mía y no está medida.
